import re
import requests
from bs4 import BeautifulSoup

filepath = '/home/russich555/Документы/my_proxies.txt'


def get_proxies_from_txt(filepath, auth_enable=False):
    """ Read proxies to list from txt"""
    with open(filepath, 'r') as f:
        if auth_enable:
            proxies_list = []
            for line in f.readlines():
                proxy = line.replace('\n', '')
                if re.search(r'.+:.+@.+:\d+', proxy):
                    proxies_list.append(proxy)
                else:
                    raise Exception(f'Invalid proxy with auth from {filepath}')
            return proxies_list
        else:
            return [line.replace('\n', '').split('@')[1] for line in f.readlines()]


def get_proxies_for_requests(filepath, auth_enable=False):
    """ Return list of dicts like that
    {'scheme': 'protocol://ip:port'} or {'scheme': 'protocol://login:pass@ip:port'} """
    return [{'https': f'http://{proxy}'} for proxy in get_proxies_from_txt(filepath, auth_enable)]


def test_ip(proxy, url):
    r = requests.get(f'https://{url}', proxies=proxy, timeout=3)
    match url:
        case 'icanhazip.com':
            return r.text
        case '2ip.ru':
            return BeautifulSoup(r.text, 'lxml').find('div', class_='ip',).find('span').text


def test_proxies(filepath, auth_enable=False):
    proxies = get_proxies_for_requests(filepath, auth_enable=auth_enable)
    for proxy in proxies:
        try:
            ip = test_ip(proxy, url='2ip.ru')
            if ip == proxy['https'][7:].split(':')[0]:
                print(ip, True)
            else:
                print(ip, False)
        except:
            print(proxy, False)


def main():
    test_proxies(filepath)


if __name__ == '__main__':
    main()
