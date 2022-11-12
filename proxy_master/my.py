import re
import json


def get_proxies_from_file(filepath: str, auth_enable: bool = False):
    """ Read proxies to list from txt|json """
    match filepath.split('.')[-1]:
        case 'txt':
            with open(filepath, 'r') as f:
                if auth_enable:
                    proxies_list = []
                    for line in f.readlines():
                        proxy = line.replace('\n', '')
                        if re.search(r'.+:.+@.+:\d+', proxy):
                            proxies_list.append(proxy)
                        else:
                            raise Exception(f'Invalid proxy with auth from {filepath}.\n'
                                            f'Sample of row: login:password@ip:port')
                    return proxies_list
                else:
                    return [line.replace('\n', '').split('@')[1] for line in f.readlines()]
        case 'json':
            with open(filepath, 'r') as f:
                data = json.load(f)
            if auth_enable:
                return data['my_proxies']
            else:
                return [proxy.split('@')[1] for proxy in data['my_proxies']]


def get_proxies_for_requests(proxies):
    """ Return list of dicts like that
    {'scheme': 'protocol://ip:port'} or {'scheme': 'protocol://login:pass@ip:port'} """
    return [{'https': f'http://{proxy}'} for proxy in proxies]