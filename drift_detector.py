"""
Drift detection engine
Compares current Terraform state against baseline snapshots
"""
from typing import Dict, List, Any, Tuple
from models import Database, StateSnapshot, Baseline, DriftEvent, Resource


class DriftDetector:
    """Detects drift between current state and baseline"""
    
    def __init__(self, db: Database):
        self.db = db
        self.snapshot_model = StateSnapshot(db)
        self.baseline_model = Baseline(db)
        self.drift_model = DriftEvent(db)
        self.resource_model = Resource(db)
    
    def detect_drift(self, snapshot_id: int, baseline_id: int) -> List[Dict[str, Any]]:
        """
        Detect drift between a snapshot and baseline
        
        Args:
            snapshot_id: Current state snapshot ID
            baseline_id: Baseline ID to compare against
            
        Returns:
            List of drift events detected
        """
        # Get snapshot and baseline
        snapshot = self.snapshot_model.get_by_id(snapshot_id)
        baseline = self.baseline_model.get_by_project_env(
            snapshot['project_id'],
            snapshot['environment_id']
        )
        
        if not baseline:
            return []
        
        baseline_snapshot = self.snapshot_model.get_by_id(baseline['snapshot_id'])
        
        # Get resources for both snapshots
        current_resources = self.resource_model.get_by_snapshot(snapshot_id)
        baseline_resources = self.resource_model.get_by_snapshot(baseline['snapshot_id'])
        
        # Detect drift
        drift_events = []
        
        # Create resource maps for comparison
        current_map = self._create_resource_map(current_resources)
        baseline_map = self._create_resource_map(baseline_resources)
        
        # Find added resources
        for key, resource in current_map.items():
            if key not in baseline_map:
                event_id = self.drift_model.create(
                    snapshot_id=snapshot_id,
                    baseline_id=baseline_id,
                    drift_type='added',
                    resource_type=resource['resource_type'],
                    resource_name=resource['resource_name'],
                    details=f"New resource added: {resource['resource_type']}.{resource['resource_name']}"
                )
                drift_events.append({
                    'id': event_id,
                    'drift_type': 'added',
                    'resource_type': resource['resource_type'],
                    'resource_name': resource['resource_name']
                })
        
        # Find removed resources
        for key, resource in baseline_map.items():
            if key not in current_map:
                event_id = self.drift_model.create(
                    snapshot_id=snapshot_id,
                    baseline_id=baseline_id,
                    drift_type='removed',
                    resource_type=resource['resource_type'],
                    resource_name=resource['resource_name'],
                    details=f"Resource removed: {resource['resource_type']}.{resource['resource_name']}"
                )
                drift_events.append({
                    'id': event_id,
                    'drift_type': 'removed',
                    'resource_type': resource['resource_type'],
                    'resource_name': resource['resource_name']
                })
        
        # Check for resource count changes by type
        current_type_counts = self._get_type_counts(current_resources)
        baseline_type_counts = self._get_type_counts(baseline_resources)
        
        for resource_type, current_count in current_type_counts.items():
            baseline_count = baseline_type_counts.get(resource_type, 0)
            if current_count != baseline_count:
                diff = current_count - baseline_count
                event_id = self.drift_model.create(
                    snapshot_id=snapshot_id,
                    baseline_id=baseline_id,
                    drift_type='count_change',
                    resource_type=resource_type,
                    resource_name='',
                    details=f"Resource count changed: {resource_type} ({baseline_count} → {current_count}, {diff:+d})"
                )
                drift_events.append({
                    'id': event_id,
                    'drift_type': 'count_change',
                    'resource_type': resource_type,
                    'count_change': diff
                })
        
        return drift_events
    
    def _create_resource_map(self, resources: List[Dict]) -> Dict[str, Dict]:
        """Create a map of resources keyed by type.name"""
        resource_map = {}
        for resource in resources:
            key = f"{resource['resource_type']}.{resource['resource_name']}"
            resource_map[key] = resource
        return resource_map
    
    def _get_type_counts(self, resources: List[Dict]) -> Dict[str, int]:
        """Get count of resources by type"""
        type_counts = {}
        for resource in resources:
            resource_type = resource['resource_type']
            type_counts[resource_type] = type_counts.get(resource_type, 0) + 1
        return type_counts
    
    def compare_snapshots(self, snapshot1_id: int, snapshot2_id: int) -> Dict[str, Any]:
        """
        Compare two snapshots and return detailed differences
        
        Args:
            snapshot1_id: First snapshot ID
            snapshot2_id: Second snapshot ID
            
        Returns:
            Dictionary containing comparison results
        """
        snapshot1 = self.snapshot_model.get_by_id(snapshot1_id)
        snapshot2 = self.snapshot_model.get_by_id(snapshot2_id)
        
        if not snapshot1 or not snapshot2:
            return {'error': 'One or both snapshots not found'}
        
        resources1 = self.resource_model.get_by_snapshot(snapshot1_id)
        resources2 = self.resource_model.get_by_snapshot(snapshot2_id)
        
        map1 = self._create_resource_map(resources1)
        map2 = self._create_resource_map(resources2)
        
        # Find differences
        added = []
        removed = []
        common = []
        
        for key, resource in map2.items():
            if key not in map1:
                added.append({
                    'type': resource['resource_type'],
                    'name': resource['resource_name']
                })
            else:
                common.append({
                    'type': resource['resource_type'],
                    'name': resource['resource_name']
                })
        
        for key, resource in map1.items():
            if key not in map2:
                removed.append({
                    'type': resource['resource_type'],
                    'name': resource['resource_name']
                })
        
        return {
            'snapshot1': {
                'id': snapshot1_id,
                'uploaded_at': snapshot1['uploaded_at'],
                'resource_count': len(resources1)
            },
            'snapshot2': {
                'id': snapshot2_id,
                'uploaded_at': snapshot2['uploaded_at'],
                'resource_count': len(resources2)
            },
            'added': added,
            'removed': removed,
            'common': common,
            'summary': {
                'added_count': len(added),
                'removed_count': len(removed),
                'common_count': len(common),
                'total_changes': len(added) + len(removed)
            }
        }
    
    def get_drift_summary(self, project_id: int = None, environment_id: int = None) -> Dict[str, Any]:
        """
        Get summary of drift events
        
        Args:
            project_id: Optional project filter
            environment_id: Optional environment filter
            
        Returns:
            Drift summary statistics
        """
        all_events = self.drift_model.get_all()
        
        # Filter if needed
        if project_id or environment_id:
            filtered_events = []
            for event in all_events:
                snapshot = self.snapshot_model.get_by_id(event['snapshot_id'])
                if project_id and snapshot['project_id'] != project_id:
                    continue
                if environment_id and snapshot['environment_id'] != environment_id:
                    continue
                filtered_events.append(event)
            all_events = filtered_events
        
        # Calculate statistics
        drift_by_type = {}
        for event in all_events:
            drift_type = event['drift_type']
            drift_by_type[drift_type] = drift_by_type.get(drift_type, 0) + 1
        
        return {
            'total_events': len(all_events),
            'by_type': drift_by_type,
            'recent_events': all_events[:10]  # Last 10 events
        }
    
    def calculate_drift_score(self, snapshot_id: int, baseline_id: int) -> float:
        """
        Calculate a drift score (0-100) indicating how much drift exists
        
        Args:
            snapshot_id: Current snapshot ID
            baseline_id: Baseline ID
            
        Returns:
            Drift score (0 = no drift, 100 = complete drift)
        """
        snapshot = self.snapshot_model.get_by_id(snapshot_id)
        baseline = self.baseline_model.get_by_project_env(
            snapshot['project_id'],
            snapshot['environment_id']
        )
        
        if not baseline:
            return 0.0
        
        baseline_snapshot = self.snapshot_model.get_by_id(baseline['snapshot_id'])
        
        current_resources = self.resource_model.get_by_snapshot(snapshot_id)
        baseline_resources = self.resource_model.get_by_snapshot(baseline['snapshot_id'])
        
        if not baseline_resources:
            return 0.0
        
        current_map = self._create_resource_map(current_resources)
        baseline_map = self._create_resource_map(baseline_resources)
        
        # Count changes
        added = len([k for k in current_map if k not in baseline_map])
        removed = len([k for k in baseline_map if k not in current_map])
        total_changes = added + removed
        
        # Calculate score based on percentage of resources changed
        baseline_count = len(baseline_resources)
        if baseline_count == 0:
            return 0.0
        
        drift_percentage = (total_changes / baseline_count) * 100
        
        # Cap at 100
        return min(drift_percentage, 100.0)
