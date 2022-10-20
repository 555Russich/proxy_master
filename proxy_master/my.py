import re


def get_proxies_from_txt(filepath='/home/russich555/Documents/my_proxies.txt', auth_enable=False):
    """ Read proxies to list from txt """
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


def get_proxies_for_requests(proxies):
    """ Return list of dicts like that
    {'scheme': 'protocol://ip:port'} or {'scheme': 'protocol://login:pass@ip:port'} """
    return [{'https': f'http://{proxy}'} for proxy in proxies]
