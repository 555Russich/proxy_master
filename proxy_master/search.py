import json
import re
from math import ceil
from datetime import datetime, timedelta
import asyncio
from aiohttp import ClientSession, ClientResponse
from bs4 import BeautifulSoup

filepath = '/home/russich555/Documents/proxies.json'
URLS_TO_TEST_PROXY = [
    'icanhazip.com',
    '2ip.ru'
]
RESOURCES_FREE_PROXIES = {
    'free-proxy-list.net': {'update_after': '20'},
    # 'hidemy.name'
    # 'geonode.com'
}


async def async_test_proxies(proxies: list, url: str = 'icanhazip.com', enable_prints: bool = False) -> list:
    def is_proxy_works(html: str, proxy: str, url: str, enable_prints: bool) -> bool:
        match url:
            case 'icanhazip.com':
                ip = html.strip()
            case '2ip.ru':
                ip = BeautifulSoup(html, 'lxml').find('div', class_='ip', ).find('span').text
            case unexpected_url:
                raise Exception(f'Unable to check ip address from {unexpected_url}.'
                                f' Use one of {URLS_TO_TEST_PROXY=}')
        if ip == proxy.split(':')[0]:
            print(f'Working! Proxy: {proxy}') if enable_prints else ...
            return True
        else:
            # print(f'NOT working :( Proxy: {proxy}') if enable_prints else ...
            return False

    proxies_works = []
    async with ClientSession() as s:
        tasks = [asyncio.create_task(session_request(s, url, proxy)) for proxy in proxies]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i in range(len(results)):
            res = results[i]
            if type(res) is str:
                if is_proxy_works(res, proxies[i], url, enable_prints) is True:
                    proxies_works.append(proxies[i])
    print(f'{len(proxies_works)}/{len(proxies)} proxies works') if enable_prints else ...
    return proxies_works


async def async_scrap_free_proxies(enable_prints: bool = False):
    proxies = []

    async def scrap_proxies_from_resource(resource: str):
        update_after = RESOURCES_FREE_PROXIES[resource]['update_after']
        match resource:
            case 'free-proxy-list.net':
                async with ClientSession() as s:
                    r = await session_request(s, resource)
                    proxies, updated_at = parse_proxies_from_html(r, resource)
                    append_proxies_from_resource(resource, proxies, updated_at, '20')
            case 'hidemy.name':
                headers = {
                    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
                    "accept-encoding": "gzip, deflate, utf-8",
                    "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                    'sec-ch-ua': '"Google Chrome";v="107", "Chromium";v="107", "Not=A?Brand";v="24"',
                    'sec-ch-ua-mobile': '?0',
                    'sec-ch-ua-platform': '"Linux"',
                    'sec-fetch-dest': 'document',
                    'sec-fetch-mode': 'navigate',
                    'sec-fetch-site': 'none',
                    'sec-fetch-user': '?1',
                    'upgrade-insecure-requests': '1',
                    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36"
                }
                r = await session_request(s, f'{resource}/en/proxy-list/', headers=headers)
                last_pagination = int(BeautifulSoup(r, 'lxml').find('div', class_='pagination').find_all('li')[-2].text)
                return [
                    session_request(s, f'{resource}/en/proxy-list/?start={i*64}', headers=headers)
                    for i in range(last_pagination)
                ]
            case 'geonode.com':
                url = 'proxylist.geonode.com/api/proxy-list'
                tasks = []
                proxies_count = 10050
                params = {
                    "limit": 300,
                    "page": 0,
                    "sort_by": "lastChecked",
                    "sort_type": "desc"
                }
                pages = ceil(proxies_count / params['limit']) + 1
                for i in range(1, pages):
                    params['page'] = i
                    tasks.append(session_request(s, url, params=params, return_json=True))
        return proxies

    def parse_proxies_from_html(html: str, resource: str):
        match resource:
            case 'free-proxy-list.net':
                soup = BeautifulSoup(html, 'lxml')
                matches = re.findall(
                    r'^((\d{1,3}\.){3}\d{1,3}:\d{1,5})$', soup.find('textarea', class_='form-control').text,
                    flags=re.MULTILINE
                )
                updated_at = datetime.strptime(re.search(
                    r'Updated at (.+ UTC)', soup.find('textarea', class_='form-control').text
                ).group(1), '%Y-%m-%d %H:%M:%S %Z')
                return [l[0] for l in matches], updated_at
            case 'hidemy.name':
                ...
            case unexpected_url:
                raise Exception(f'Unable to find free proxies on {unexpected_url}.\n'
                                f'List which available: {RESOURCES_FREE_PROXIES}')

    def append_proxies_from_resource(resource: str, data2append, updated_at: datetime, update_after: str) -> None:
        with open(filepath, 'r') as f:
            data = json.load(f)
        data[resource] = {
            'last_update': updated_at.strftime('%Y-%m-%d %H:%M:%S'),
            'update_after': update_after,
            'data': data2append
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)

    def is_update_needed(resource: str) -> bool:
        with open(filepath, 'r') as f:
            data = json.load(f)
        last_update = datetime.strptime(data[resource]['last_update'], '%Y-%m-%d %H:%M:%S')
        updated_after = int(data[resource]['update_after'])
        return True if datetime.utcnow() - timedelta(minutes=updated_after) > last_update else False

    def read_cached_proxies(resource: str) -> list:
        with open(filepath, 'r') as f:
            return json.load(f)[resource]['data']

    for resource in RESOURCES_FREE_PROXIES:
        if is_update_needed(resource):
            print(f'Scrapping proxies from {resource}')
            proxies_ = await scrap_proxies_from_resource(resource)
        else:
            print(f'Read cached {resource} proxies')
            proxies_ = read_cached_proxies(resource)
        for proxy in proxies_:
            proxies.append(proxy)
    return proxies


async def session_request(
        s: ClientSession,
        url: str,
        proxy: str = None,
        headers: dict = None,
        params: dict = None,
        json_: dict = None,
        return_json: bool = False,
        timeout: int = 3
) -> ClientResponse | str:
    async with s.get(
            f'https://{url}',
            proxy=f'http://{proxy}' if proxy else None,
            headers=headers if headers else None,
            json=json_ if json_ else None,
            params=params if params else None,
            timeout=timeout
    ) as r:
        match r.status:
            case 200:
                return str(await r.text()) if not return_json else await r.json()
            case _:
                return r


def test_proxies(proxies: list, url: str = 'icanhazip.com', enable_prints: bool = False):
    """ Sync call of test_proxies """
    return asyncio.run(async_test_proxies(proxies, url, enable_prints))


def scrap_free_proxies(enable_prints: bool = False):
    """ Sync call of scrap_free_proxies """
    return asyncio.run(async_scrap_free_proxies(enable_prints=enable_prints))


if __name__ == '__main__':
    from my import get_proxies_from_file
    # print(test_proxies(scrap_free_proxies(enable_prints=True), enable_prints=True))
    print(scrap_free_proxies(enable_prints=True))