"""
TerraState Guardian - Flask Application
Self-hosted Terraform state monitoring and drift detection
"""
import os
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.utils import secure_filename

from models import (
    Database, User, Project, Environment, StateSnapshot, 
    Baseline, DriftEvent, Resource
)
from state_parser import TerraformStateParser
from drift_detector import DriftDetector
from auth import init_auth, login_required, login_user, logout_user, authenticate, get_current_user

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_UPLOAD_SIZE', 10 * 1024 * 1024))  # 10MB default
app.config['UPLOAD_FOLDER'] = 'uploads'

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize database
db = Database()
init_auth(app)


# ============================================================================
# Authentication Routes
# ============================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        success, result = authenticate(username, password, db)
        
        if success:
            login_user(result['id'], result['username'])
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash(result.get('error', 'Login failed'), 'danger')
    
    return render_template('login.html')


@app.route('/logout')
def logout():
    """Logout current user"""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


# ============================================================================
# Main Application Routes
# ============================================================================

@app.route('/')
@login_required
def index():
    """Redirect to dashboard"""
    return redirect(url_for('dashboard'))


@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard showing overview of all projects and environments"""
    project_model = Project(db)
    env_model = Environment(db)
    snapshot_model = StateSnapshot(db)
    drift_model = DriftEvent(db)
    
    projects = project_model.get_all()
    environments = env_model.get_all()
    recent_snapshots = snapshot_model.get_all()[:10]
    recent_drift = drift_model.get_all()[:10]
    
    # Calculate statistics
    total_snapshots = len(snapshot_model.get_all())
    total_drift_events = len(drift_model.get_all())
    
    # Get resource counts by environment
    env_stats = {}
    for env in environments:
        snapshots = [s for s in recent_snapshots if s.get('environment_id') == env['id']]
        total_resources = sum(s.get('resource_count', 0) for s in snapshots)
        env_stats[env['name']] = {
            'snapshots': len(snapshots),
            'resources': total_resources
        }
    
    return render_template(
        'dashboard.html',
        user=get_current_user(),
        projects=projects,
        environments=environments,
        recent_snapshots=recent_snapshots,
        recent_drift=recent_drift,
        total_snapshots=total_snapshots,
        total_drift_events=total_drift_events,
        env_stats=env_stats
    )


@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    """Upload Terraform state file"""
    project_model = Project(db)
    env_model = Environment(db)
    snapshot_model = StateSnapshot(db)
    baseline_model = Baseline(db)
    resource_model = Resource(db)
    
    if request.method == 'POST':
        # Get form data
        project_name = request.form.get('project_name')
        new_project_name = request.form.get('new_project_name')
        project_description = request.form.get('project_description', '')
        environment_name = request.form.get('environment')
        
        # Handle new project creation
        if new_project_name:
            project_name = new_project_name
            try:
                project_model.create(project_name, project_description)
                flash(f'Created new project: {project_name}', 'success')
            except Exception as e:
                flash(f'Error creating project: {str(e)}', 'danger')
                return redirect(url_for('upload'))
        
        # Get or create project and environment
        project = project_model.get_by_name(project_name)
        environment = env_model.get_by_name(environment_name)
        
        if not project or not environment:
            flash('Invalid project or environment', 'danger')
            return redirect(url_for('upload'))
        
        # Handle file upload
        if 'state_file' not in request.files:
            flash('No file uploaded', 'danger')
            return redirect(url_for('upload'))
        
        file = request.files['state_file']
        
        if file.filename == '':
            flash('No file selected', 'danger')
            return redirect(url_for('upload'))
        
        if file and file.filename.endswith('.json'):
            try:
                # Read and parse state file
                state_content = file.read().decode('utf-8')
                parser = TerraformStateParser()
                parsed_state = parser.parse(state_content)
                
                # Create snapshot
                snapshot_id = snapshot_model.create(
                    project_id=project['id'],
                    environment_id=environment['id'],
                    state_data=json.loads(state_content),
                    terraform_version=parsed_state['terraform_version'],
                    serial=parsed_state['serial'],
                    lineage=parsed_state['lineage']
                )
                
                # Store resources
                for resource in parsed_state['resources']:
                    resource_model.create(
                        snapshot_id=snapshot_id,
                        resource_type=resource['type'],
                        resource_name=resource['name'],
                        provider=resource.get('provider', ''),
                        module=resource.get('module', ''),
                        attributes=resource.get('attributes', {})
                    )
                
                # Check if baseline exists
                baseline = baseline_model.get_by_project_env(project['id'], environment['id'])
                
                if not baseline:
                    # Create baseline
                    baseline_model.create_or_update(project['id'], environment['id'], snapshot_id)
                    flash(f'State uploaded and set as baseline for {project_name}/{environment_name}', 'success')
                else:
                    # Detect drift
                    detector = DriftDetector(db)
                    drift_events = detector.detect_drift(snapshot_id, baseline['id'])
                    
                    if drift_events:
                        flash(f'State uploaded. Detected {len(drift_events)} drift event(s)', 'warning')
                    else:
                        flash('State uploaded. No drift detected', 'success')
                
                return redirect(url_for('history'))
                
            except Exception as e:
                flash(f'Error parsing state file: {str(e)}', 'danger')
                return redirect(url_for('upload'))
        else:
            flash('Invalid file type. Please upload a JSON file', 'danger')
            return redirect(url_for('upload'))
    
    # GET request
    projects = project_model.get_all()
    environments = env_model.get_all()
    
    return render_template(
        'upload.html',
        user=get_current_user(),
        projects=projects,
        environments=environments
    )


@app.route('/projects')
@login_required
def projects():
    """View all projects"""
    project_model = Project(db)
    snapshot_model = StateSnapshot(db)
    
    projects_list = project_model.get_all()
    
    # Add snapshot counts to each project
    for project in projects_list:
        snapshots = snapshot_model.get_by_project(project['id'])
        project['snapshot_count'] = len(snapshots)
        project['latest_snapshot'] = snapshots[0] if snapshots else None
    
    return render_template(
        'projects.html',
        user=get_current_user(),
        projects=projects_list
    )


@app.route('/drift')
@login_required
def drift():
    """View drift detection results"""
    drift_model = DriftEvent(db)
    project_model = Project(db)
    env_model = Environment(db)
    
    drift_events = drift_model.get_all()
    
    # Group by drift type
    drift_by_type = {}
    for event in drift_events:
        drift_type = event['drift_type']
        if drift_type not in drift_by_type:
            drift_by_type[drift_type] = []
        drift_by_type[drift_type].append(event)
    
    return render_template(
        'drift.html',
        user=get_current_user(),
        drift_events=drift_events,
        drift_by_type=drift_by_type
    )


@app.route('/history')
@login_required
def history():
    """View change history timeline"""
    snapshot_model = StateSnapshot(db)
    
    snapshots = snapshot_model.get_all()
    
    return render_template(
        'history.html',
        user=get_current_user(),
        snapshots=snapshots
    )


@app.route('/compare')
@login_required
def compare():
    """Compare two state snapshots"""
    snapshot_model = StateSnapshot(db)
    
    snapshot1_id = request.args.get('snapshot1', type=int)
    snapshot2_id = request.args.get('snapshot2', type=int)
    
    snapshots = snapshot_model.get_all()
    comparison = None
    
    if snapshot1_id and snapshot2_id:
        detector = DriftDetector(db)
        comparison = detector.compare_snapshots(snapshot1_id, snapshot2_id)
    
    return render_template(
        'compare.html',
        user=get_current_user(),
        snapshots=snapshots,
        comparison=comparison,
        snapshot1_id=snapshot1_id,
        snapshot2_id=snapshot2_id
    )


@app.route('/resources')
@login_required
def resources():
    """View all resources inventory"""
    resource_model = Resource(db)
    
    all_resources = resource_model.get_all()
    
    # Group by resource type
    resources_by_type = {}
    for resource in all_resources:
        resource_type = resource['resource_type']
        if resource_type not in resources_by_type:
            resources_by_type[resource_type] = []
        resources_by_type[resource_type].append(resource)
    
    return render_template(
        'resources.html',
        user=get_current_user(),
        resources=all_resources,
        resources_by_type=resources_by_type
    )


# ============================================================================
# API Routes
# ============================================================================

@app.route('/api/projects')
@login_required
def api_projects():
    """API: Get all projects"""
    project_model = Project(db)
    projects = project_model.get_all()
    return jsonify(projects)


@app.route('/api/snapshots/<int:project_id>')
@login_required
def api_snapshots(project_id):
    """API: Get snapshots for a project"""
    snapshot_model = StateSnapshot(db)
    snapshots = snapshot_model.get_by_project(project_id)
    
    # Remove large state_data from response
    for snapshot in snapshots:
        snapshot.pop('state_data', None)
    
    return jsonify(snapshots)


@app.route('/api/drift-events')
@login_required
def api_drift_events():
    """API: Get all drift events"""
    drift_model = DriftEvent(db)
    events = drift_model.get_all()
    return jsonify(events)


@app.route('/api/resources')
@login_required
def api_resources():
    """API: Get all resources"""
    resource_model = Resource(db)
    resources = resource_model.get_all()
    
    # Remove large attributes from response
    for resource in resources:
        resource.pop('attributes', None)
    
    return jsonify(resources)


@app.route('/api/compare/<int:snapshot1_id>/<int:snapshot2_id>')
@login_required
def api_compare(snapshot1_id, snapshot2_id):
    """API: Compare two snapshots"""
    detector = DriftDetector(db)
    comparison = detector.compare_snapshots(snapshot1_id, snapshot2_id)
    return jsonify(comparison)


@app.route('/api/export-drift')
@login_required
def api_export_drift():
    """API: Export drift report"""
    drift_model = DriftEvent(db)
    events = drift_model.get_all()
    
    report = {
        'generated_at': datetime.now().isoformat(),
        'total_events': len(events),
        'events': events
    }
    
    return jsonify(report)


@app.route('/api/parse-state', methods=['POST'])
@login_required
def api_parse_state():
    """API: Parse a Terraform state file"""
    if 'state_file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['state_file']
    
    try:
        state_content = file.read().decode('utf-8')
        parser = TerraformStateParser()
        parsed_state = parser.parse(state_content)
        
        # Remove full state data from response
        parsed_state.pop('resources', None)
        
        return jsonify(parsed_state)
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/detect-drift', methods=['POST'])
@login_required
def api_detect_drift():
    """API: Trigger drift detection"""
    data = request.get_json()
    
    snapshot_id = data.get('snapshot_id')
    baseline_id = data.get('baseline_id')
    
    if not snapshot_id or not baseline_id:
        return jsonify({'error': 'Missing snapshot_id or baseline_id'}), 400
    
    try:
        detector = DriftDetector(db)
        drift_events = detector.detect_drift(snapshot_id, baseline_id)
        return jsonify({'events': drift_events})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Error Handlers
# ============================================================================

@app.errorhandler(404)
def not_found(e):
    """404 error handler"""
    return render_template('404.html', user=get_current_user()), 404


@app.errorhandler(500)
def server_error(e):
    """500 error handler"""
    return render_template('500.html', user=get_current_user()), 500


# ============================================================================
# Main
# ============================================================================

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV', 'development') == 'development'
    
    print("=" * 60)
    print("TerraState Guardian")
    print("Self-hosted Terraform state monitoring and drift detection")
    print("=" * 60)
    print(f"\nStarting server on http://localhost:{port}")
    print("\nDefault login credentials:")
    print("  Username: admin")
    print("  Password: admin123")
    print("\nPress CTRL+C to stop the server")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=port, debug=debug)
