"""
Terraform state file parser
Extracts resources and metadata from Terraform JSON state files
"""
import json
from typing import Dict, List, Any, Optional


class TerraformStateParser:
    """Parser for Terraform state JSON files"""
    
    def __init__(self):
        self.state_data = None
        self.resources = []
    
    def parse(self, state_json: str) -> Dict[str, Any]:
        """
        Parse Terraform state JSON string
        
        Args:
            state_json: JSON string of Terraform state
            
        Returns:
            Dictionary containing parsed state information
        """
        try:
            self.state_data = json.loads(state_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {str(e)}")
        
        if not isinstance(self.state_data, dict):
            raise ValueError("State file must be a JSON object")
        
        # Extract metadata
        version = self.state_data.get('version', 0)
        terraform_version = self.state_data.get('terraform_version', 'unknown')
        serial = self.state_data.get('serial', 0)
        lineage = self.state_data.get('lineage', '')
        
        # Parse resources
        self.resources = self._extract_resources()
        
        return {
            'version': version,
            'terraform_version': terraform_version,
            'serial': serial,
            'lineage': lineage,
            'resources': self.resources,
            'resource_count': len(self.resources)
        }
    
    def _extract_resources(self) -> List[Dict[str, Any]]:
        """Extract resources from state data"""
        resources = []
        
        # Handle Terraform 0.12+ format
        if 'resources' in self.state_data:
            for resource in self.state_data['resources']:
                resources.extend(self._parse_resource_v4(resource))
        
        # Handle older Terraform format
        elif 'modules' in self.state_data:
            for module in self.state_data['modules']:
                if 'resources' in module:
                    for key, resource in module['resources'].items():
                        resources.append(self._parse_resource_v3(key, resource, module))
        
        return resources
    
    def _parse_resource_v4(self, resource: Dict) -> List[Dict[str, Any]]:
        """Parse Terraform 0.12+ resource format"""
        parsed_resources = []
        
        resource_type = resource.get('type', 'unknown')
        resource_name = resource.get('name', 'unknown')
        provider = resource.get('provider', '')
        module = resource.get('module', '')
        mode = resource.get('mode', 'managed')
        
        # Handle instances (for count/for_each)
        instances = resource.get('instances', [])
        
        if not instances:
            # No instances, create single resource entry
            parsed_resources.append({
                'type': resource_type,
                'name': resource_name,
                'provider': provider,
                'module': module,
                'mode': mode,
                'index': None,
                'attributes': {}
            })
        else:
            for idx, instance in enumerate(instances):
                index_key = instance.get('index_key')
                attributes = instance.get('attributes', {})
                
                parsed_resources.append({
                    'type': resource_type,
                    'name': resource_name,
                    'provider': provider,
                    'module': module,
                    'mode': mode,
                    'index': index_key,
                    'attributes': self._sanitize_attributes(attributes)
                })
        
        return parsed_resources
    
    def _parse_resource_v3(self, key: str, resource: Dict, module: Dict) -> Dict[str, Any]:
        """Parse Terraform 0.11 and earlier resource format"""
        # Key format: resource_type.resource_name or resource_type.resource_name.index
        parts = key.split('.')
        resource_type = parts[0] if len(parts) > 0 else 'unknown'
        resource_name = parts[1] if len(parts) > 1 else 'unknown'
        index = parts[2] if len(parts) > 2 else None
        
        return {
            'type': resource_type,
            'name': resource_name,
            'provider': resource.get('provider', ''),
            'module': module.get('path', ['root'])[-1],
            'mode': 'managed',
            'index': index,
            'attributes': self._sanitize_attributes(resource.get('primary', {}).get('attributes', {}))
        }
    
    def _sanitize_attributes(self, attributes: Dict) -> Dict:
        """Sanitize attributes to remove sensitive data and reduce size"""
        # Only keep basic identifying attributes
        safe_attrs = {}
        
        # Common safe attributes to preserve
        safe_keys = ['id', 'name', 'arn', 'region', 'zone', 'type', 'size', 'tags']
        
        for key in safe_keys:
            if key in attributes:
                value = attributes[key]
                # Limit string length
                if isinstance(value, str) and len(value) > 200:
                    safe_attrs[key] = value[:200] + '...'
                else:
                    safe_attrs[key] = value
        
        return safe_attrs
    
    def get_resource_types(self) -> Dict[str, int]:
        """Get count of resources by type"""
        type_counts = {}
        
        for resource in self.resources:
            resource_type = resource['type']
            type_counts[resource_type] = type_counts.get(resource_type, 0) + 1
        
        return type_counts
    
    def get_providers(self) -> List[str]:
        """Get list of unique providers"""
        providers = set()
        
        for resource in self.resources:
            if resource.get('provider'):
                providers.add(resource['provider'])
        
        return sorted(list(providers))
    
    def get_modules(self) -> List[str]:
        """Get list of unique modules"""
        modules = set()
        
        for resource in self.resources:
            if resource.get('module'):
                modules.add(resource['module'])
        
        return sorted(list(modules))
    
    def validate_state(self) -> tuple[bool, Optional[str]]:
        """
        Validate that the state file is properly formatted
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.state_data:
            return False, "No state data loaded"
        
        # Check for required fields
        if 'version' not in self.state_data and 'terraform_version' not in self.state_data:
            return False, "Missing version information"
        
        # Check for resources or modules
        if 'resources' not in self.state_data and 'modules' not in self.state_data:
            return False, "No resources or modules found in state"
        
        return True, None


def parse_terraform_state(state_json: str) -> Dict[str, Any]:
    """
    Convenience function to parse Terraform state
    
    Args:
        state_json: JSON string of Terraform state
        
    Returns:
        Parsed state dictionary
    """
    parser = TerraformStateParser()
    return parser.parse(state_json)


def create_sample_state(resource_count: int = 5) -> Dict[str, Any]:
    """
    Create a sample Terraform state for testing
    
    Args:
        resource_count: Number of sample resources to create
        
    Returns:
        Sample state dictionary
    """
    resources = []
    
    resource_types = [
        'aws_instance',
        'aws_s3_bucket',
        'aws_vpc',
        'aws_security_group',
        'aws_rds_instance',
        'aws_lambda_function',
        'aws_dynamodb_table'
    ]
    
    for i in range(resource_count):
        resource_type = resource_types[i % len(resource_types)]
        resources.append({
            'mode': 'managed',
            'type': resource_type,
            'name': f'example_{i}',
            'provider': 'provider["registry.terraform.io/hashicorp/aws"]',
            'instances': [
                {
                    'schema_version': 0,
                    'attributes': {
                        'id': f'{resource_type}-{i}',
                        'name': f'example-{i}',
                        'arn': f'arn:aws:service:us-east-1:123456789012:{resource_type}/{i}',
                        'tags': {'Environment': 'dev', 'ManagedBy': 'Terraform'}
                    }
                }
            ]
        })
    
    return {
        'version': 4,
        'terraform_version': '1.5.0',
        'serial': 1,
        'lineage': 'sample-lineage-uuid',
        'resources': resources
    }
