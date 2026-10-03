"""
Database seeding script
Creates initial data for development and testing
"""
import json
from models import Database, User, Project, Environment, StateSnapshot, Baseline, Resource
from state_parser import create_sample_state


def seed_database():
    """Seed the database with initial data"""
    print("Initializing database...")
    db = Database()
    
    # Create models
    user_model = User(db)
    project_model = Project(db)
    env_model = Environment(db)
    snapshot_model = StateSnapshot(db)
    baseline_model = Baseline(db)
    resource_model = Resource(db)
    
    print("Creating default user...")
    # Create default user
    try:
        user_model.create('admin', 'admin123')
        print("✓ Created user: admin / admin123")
    except Exception as e:
        print(f"User already exists or error: {e}")
    
    print("\nCreating environments...")
    # Create environments
    environments = ['dev', 'staging', 'prod']
    env_ids = {}
    
    for env_name in environments:
        try:
            env_id = env_model.create(
                env_name,
                f"{env_name.capitalize()} environment"
            )
            env_ids[env_name] = env_id
            print(f"✓ Created environment: {env_name}")
        except Exception as e:
            existing = env_model.get_by_name(env_name)
            if existing:
                env_ids[env_name] = existing['id']
                print(f"Environment {env_name} already exists")
    
    print("\nCreating projects...")
    # Create sample projects
    projects_data = [
        {
            'name': 'web-application',
            'description': 'Main web application infrastructure'
        },
        {
            'name': 'data-pipeline',
            'description': 'ETL and data processing infrastructure'
        },
        {
            'name': 'monitoring',
            'description': 'Monitoring and observability stack'
        }
    ]
    
    project_ids = {}
    for proj_data in projects_data:
        try:
            proj_id = project_model.create(proj_data['name'], proj_data['description'])
            project_ids[proj_data['name']] = proj_id
            print(f"✓ Created project: {proj_data['name']}")
        except Exception as e:
            existing = project_model.get_by_name(proj_data['name'])
            if existing:
                project_ids[proj_data['name']] = existing['id']
                print(f"Project {proj_data['name']} already exists")
    
    print("\nCreating state snapshots...")
    # Create sample state snapshots
    snapshot_configs = [
        # Web application - dev
        {
            'project': 'web-application',
            'environment': 'dev',
            'resource_count': 8,
            'is_baseline': True
        },
        {
            'project': 'web-application',
            'environment': 'dev',
            'resource_count': 10,  # Added 2 resources (drift)
            'is_baseline': False
        },
        # Web application - staging
        {
            'project': 'web-application',
            'environment': 'staging',
            'resource_count': 12,
            'is_baseline': True
        },
        # Web application - prod
        {
            'project': 'web-application',
            'environment': 'prod',
            'resource_count': 15,
            'is_baseline': True
        },
        # Data pipeline - dev
        {
            'project': 'data-pipeline',
            'environment': 'dev',
            'resource_count': 6,
            'is_baseline': True
        },
        {
            'project': 'data-pipeline',
            'environment': 'dev',
            'resource_count': 5,  # Removed 1 resource (drift)
            'is_baseline': False
        },
        # Monitoring - prod
        {
            'project': 'monitoring',
            'environment': 'prod',
            'resource_count': 7,
            'is_baseline': True
        }
    ]
    
    for config in snapshot_configs:
        project_name = config['project']
        env_name = config['environment']
        
        if project_name not in project_ids or env_name not in env_ids:
            continue
        
        # Create sample state
        state_data = create_sample_state(config['resource_count'])
        
        # Create snapshot
        snapshot_id = snapshot_model.create(
            project_id=project_ids[project_name],
            environment_id=env_ids[env_name],
            state_data=state_data,
            terraform_version=state_data['terraform_version'],
            serial=state_data['serial'],
            lineage=state_data['lineage']
        )
        
        # Create resources
        for resource in state_data['resources']:
            for instance in resource.get('instances', []):
                resource_model.create(
                    snapshot_id=snapshot_id,
                    resource_type=resource['type'],
                    resource_name=resource['name'],
                    provider=resource.get('provider', ''),
                    module=resource.get('module', ''),
                    attributes=instance.get('attributes', {})
                )
        
        # Set as baseline if configured
        if config['is_baseline']:
            baseline_model.create_or_update(
                project_id=project_ids[project_name],
                environment_id=env_ids[env_name],
                snapshot_id=snapshot_id
            )
            print(f"✓ Created baseline snapshot for {project_name}/{env_name} ({config['resource_count']} resources)")
        else:
            print(f"✓ Created snapshot for {project_name}/{env_name} ({config['resource_count']} resources)")
    
    print("\n✅ Database seeded successfully!")
    print("\nLogin credentials:")
    print("  Username: admin")
    print("  Password: admin123")
    print("\nYou can now run the application with: python app.py")


if __name__ == '__main__':
    seed_database()
