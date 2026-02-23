import pytest
import os
from unittest.mock import patch
from config import AppConfig

def test_config_invalid_port(mock_config):
    # Create a new config taking the same arguments but with an invalid port
    # Since email_smtp_port is an init field without a default arg (it uses default_factory)
    # Actually, we can mock os.getenv to return abc. Wait, if we mock os.getenv, AppConfig instantiation will use it.
    
    with patch('os.getenv') as mock_getenv:
        def getenv_side_effect(key, default=None):
            if key == "EMAIL_SMTP_PORT":
                return "abc"
            if key == "EMAIL_SMTP_HOST": return "smtp.gmail.com"
            if key == "EMAIL_SMTP_SSL": return "False"
            return mock_config.__getattribute__(key.lower()) if hasattr(mock_config, key.lower()) else default
            
        mock_getenv.side_effect = getenv_side_effect
        
        # Test just the port validation failure specifically
        from dataclasses import replace
        bad_config = replace(mock_config, email_smtp_port="abc")
        
        assert bad_config.validate() is False

def test_config_missing_paths(mock_config):
    # Remove the base_movies_root effectively missing the directory
    import shutil
    shutil.rmtree(mock_config.base_movies_root)
    
    assert mock_config.validate() is False
