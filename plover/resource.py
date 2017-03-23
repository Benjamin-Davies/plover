
import os

import pkg_resources


ASSET_SCHEME = 'asset:'

def _asset_split(resource_name):
    return resource_name[len(ASSET_SCHEME):].split(':', 2)

def resource_exists(resource_name):
    if resource_name.startswith(ASSET_SCHEME):
        return pkg_resources.resource_exists(*_asset_split(resource_name))
    return os.path.exists(resource_name)

def resource_filename(resource_name):
    if resource_name.startswith(ASSET_SCHEME):
        return pkg_resources.resource_filename(*_asset_split(resource_name))
    return resource_name
