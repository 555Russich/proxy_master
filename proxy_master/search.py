import re
import asyncio
import aiohttp
from bs4 import BeautifulSoup

VALIDATE_URLS = \
    [
        'icanhazip.com',
        '2ip.ru'
    ]


async def async_test_proxies(proxies, url='icanhazip.com'):
    async def get_ip(s, url, proxy):
        try:
            async with s.get(
                    f'https://{url}',
                    proxy=f'http://{proxy}',
                    timeout=3
            ) as r:
                match r.status:
                    case 200:
                        html = str(await r.text())
                        match url:
                            case 'icanhazip.com':
                                ip = html.strip()
                            case '2ip.ru':
                                ip = BeautifulSoup(html, 'lxml').find('div', class_='ip', ).find('span').text
                            case _:
                                raise Exception(f'Can\'t check ip address from this website.'
                                                f' Use one of {VALIDATE_URLS=}')
                        if ip == proxy.split(':')[0]:
                            print(f'Working! Proxy: {proxy}')
                            proxies_works.append(proxy)
                    case _:
                        print(f'Not working :( Proxy: {proxy}')
        except:
            print(f'Not working :( Proxy: {proxy}')

    proxies_works = []
    async with aiohttp.ClientSession() as s:
        tasks = [asyncio.create_task(get_ip(s, url, proxy)) for proxy in proxies]
        await asyncio.gather(*tasks)
    print(f'{len(proxies_works)}/{len(proxies)} proxies works')
    return proxies_works


async def async_find_free_proxies():
    async with aiohttp.ClientSession() as s:
        async with s.get('https://free-proxy-list.net/') as r:
            soup = BeautifulSoup(await r.text(), 'lxml')
            matches = re.findall(
                r'^((\d{1,3}\.){3}\d{1,3}:\d{1,5})$',
                soup.find('textarea', class_='form-control').text,
                flags=re.MULTILINE)
    return [l[0] for l in matches]


def test_proxies(proxies):
    return asyncio.run(async_test_proxies(proxies))


def find_free_proxies():
    return asyncio.run(async_find_free_proxies())
