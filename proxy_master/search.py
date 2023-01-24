import json
import re
from math import ceil
from datetime import datetime, timedelta
import asyncio
from aiohttp import ClientSession, ClientResponse
from bs4 import BeautifulSoup

from exceptions import CaptchaOnPageError
    

FILEPATH = '/home/russich555/Documents/proxies.json'
PATTERN_IP_PORT = r"((([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5]):\d{1,5})"
URLS_TO_TEST_PROXY = [
    'icanhazip.com',
    '2ip.ru'
]
RESOURCES_FREE_PROXIES = {
    'free-proxy-list.net': {'update_after': '15'},
    'geonode.com': {'update_after': '30'},
    'openproxy.space': {'update_after': '60'},
    'freeproxylists.net': {'update_after': '30'},
    # 'hidemy.name'
}


async def async_test_proxies(proxies: list,
                             url: str = 'icanhazip.com',
                             enable_prints: bool = False,
                             timeout=3,
                             ) -> list:
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
            return False

    proxies_works = []
    async with ClientSession() as s:
        tasks = [asyncio.create_task(session_request(s, url, proxy, timeout=timeout)) for proxy in proxies]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i in range(len(results)):
            if type(results[i]) is str:
                if is_proxy_works(results[i], proxies[i], url, enable_prints) is True:
                    proxies_works.append(proxies[i])
    print(f'{len(proxies_works)}/{len(proxies)} proxies works') if enable_prints else ...
    return proxies_works


async def async_scrap_free_proxies(enable_prints: bool = False):

    async def scrap_proxies_from_resource(resource: str):
        error_while_scrapping = False

        async with ClientSession() as s:
            match resource:
                case 'free-proxy-list.net':
                    r = await session_request(s, resource)
                    proxies, updated_at = parse_proxies_from_html(r, resource)
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
                    last_pagination = int(BeautifulSoup(r, 'lxml').find(
                        'div', class_='pagination'
                    ).find_all('li')[-2].text)
                    return [
                        session_request(s, f'{resource}/en/proxy-list/?start={i*64}', headers=headers)
                        for i in range(last_pagination)
                    ]
                case 'geonode.com':
                    proxies = set()
                    url = 'proxylist.geonode.com/api/proxy-list'
                    params = {
                        "limit": 1,
                        "page": 1,
                        "sort_by": "lastChecked",
                        "sort_type": "desc",
                        "protocols": 'https,http',
                    }
                    r = await session_request(s, url, params=params, return_json=True)
                    params['limit'] = 500
                    for page in range(1, ceil(r['total'] / params['limit']) + 1):
                        params['page'] = page
                        r = await session_request(s, url, params=params, return_json=True, timeout=20)
                        for proxy_data in r['data']:
                            proxies.add(f"{proxy_data['ip']}:{proxy_data['port']}")
                    updated_at = datetime.utcnow()
                case 'openproxy.space':
                    url = 'openproxy.space/list/http'
                    r = await session_request(s, url)
                    proxies = [t[0] for t in re.findall(PATTERN_IP_PORT, r) if '127.0.0.1' not in t[0]]
                    updated_at = datetime.utcnow()
                case 'freeproxylists.net':
                    proxies = []
                    url = 'www.freeproxylists.net/ru/'
                    headers = {
                        'authority': 'www.freeproxylists.net',
                        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
                        'accept-language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                        'cache-control': 'max-age=0',
                        'cookie': 'hl=ru; userno=20230103-000706; from=google; refdomain=www.google.com; visited=2023%2F01%2F03%2002%3A38%3A58; pv=6',
                        'origin': 'https://www.freeproxylists.net',
                        'referer': 'https://www.freeproxylists.net/ru/',
                        'sec-ch-ua': '"Not?A_Brand";v="8", "Chromium";v="108", "Google Chrome";v="108"',
                        'sec-ch-ua-mobile': '?0',
                        'sec-ch-ua-platform': '"Linux"',
                        'sec-fetch-dest': 'document',
                        'sec-fetch-mode': 'navigate',
                        'sec-fetch-site': 'same-origin',
                        'sec-fetch-user': '?1',
                        'upgrade-insecure-requests': '1',
                        'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
                    }

                    last_page = None
                    params = {'page': 1}
                    while True:
                        r = await session_request(s, url, headers=headers, params=params, timeout=10)
                        soup = BeautifulSoup(r, 'lxml')
                        
                        if not last_page:
                            last_page = int(soup.find('div', class_='page').find_all('a')[-2].text)
                        
                        if ...: # TODO test different timeouts, sometimes gets blocked.
                            # TODO identify captcha on page
                            raise CaptchaOnPageError(f'{resource=} | got proxies={len(proxies)}')

                        count_before = len(proxies)
                        proxies += parse_proxies_from_html(r, resource)
                        count_after = len(proxies)
                        print(f'{resource=} | page={params["page"]} | proxies from page: {count_after-count_before} |'
                              f'total: {len(proxies)}') if enable_prints else None

                        if params['page'] == last_page:
                            break

                        params['page'] += 1
                    updated_at = datetime.utcnow()
        return list(proxies), updated_at

    def parse_proxies_from_html(html: str, resource: str):
        soup = BeautifulSoup(html, 'lxml')
        match resource:
            case 'free-proxy-list.net':
                matches = re.findall(
                    PATTERN_IP_PORT, soup.find('textarea', class_='form-control').text
                )
                updated_at = datetime.strptime(re.search(
                    r'Updated at (.+ UTC)', soup.find('textarea', class_='form-control').text
                ).group(1), '%Y-%m-%d %H:%M:%S %Z')
                return [l[0] for l in matches], updated_at
            case 'hidemy.name':
                ...
            case 'freeproxylists.net':
                proxies = []
                for tr in soup.find('table', class_='DataGrid').find_all('tr')[1:]:
                    try:
                        ip_hex = str(tr.find_all('td')[0].string).replace('IPDecode', '')[2:-2]
                        ip = BeautifulSoup(bytearray.fromhex(ip_hex.replace('%', '')).decode(), 'lxml').text
                        port = tr.find_all('td')[1].text
                        proxies.append(f'{ip}:{port}')
                    except IndexError:
                        continue
                return proxies
            case unexpected_url:
                raise Exception(f'Unable to find free proxies on {unexpected_url}.\n'
                                f'List which available: {RESOURCES_FREE_PROXIES}')

    def append_proxies_from_resource(resource: str,
                                     data2append,
                                     updated_at: datetime,
                                     update_after: str
                                     ) -> None:
        with open(FILEPATH, 'r') as f:
            data = json.load(f)
        data[resource] = {
            'last_update': updated_at.strftime('%Y-%m-%d %H:%M:%S'),
            'update_after': update_after,
            'proxies': data2append
        }
        with open(FILEPATH, 'w') as f:
            json.dump(data, f, indent=4)

    def is_update_needed(resource: str) -> bool:
        with open(FILEPATH, 'r') as f:
            data = json.load(f)

        # Check if resource in file, otherwise append
        if not data.get(resource):
            data[resource] = {
                'last_update': None,
                'update_after': None,
                'proxies': None
            }
            with open(FILEPATH, 'w') as f:
                json.dump(data, f, indent=4)
            return True
        elif data.get(resource) and not data[resource].get('proxies'):
            return True

        last_update = datetime.strptime(data[resource]['last_update'], '%Y-%m-%d %H:%M:%S')
        updated_after = int(data[resource]['update_after'])
        return True if datetime.utcnow() - timedelta(minutes=updated_after) > last_update else False

    def read_cached_proxies(resource: str) -> list:
        print(f'Read cached {resource} proxies') if enable_prints else ...
        with open(FILEPATH, 'r') as f:
            return json.load(f)[resource]['proxies']

    proxies = []
    for resource in RESOURCES_FREE_PROXIES:
        if is_update_needed(resource):
            print(f'Scrapping proxies from {resource}') if enable_prints else ...
            try:
                resources_proxies, updated_at = await scrap_proxies_from_resource(resource)
                append_proxies_from_resource(resource, resources_proxies, updated_at,
                                             RESOURCES_FREE_PROXIES[resource]['update_after'])
            except Exception as ex:
                print(f'Error while scrapping proxies from {resource}.\n{ex}')
                resources_proxies = read_cached_proxies(resource)
        else:
            resources_proxies = read_cached_proxies(resource)

        for proxy in resources_proxies:
            proxies.append(proxy)

    return proxies


async def session_request(s: ClientSession,
                          url: str,
                          proxy: str = None,
                          headers: dict = None,
                          params: dict = None,
                          json_: dict = None,
                          return_json: bool = False,
                          timeout: int = 3
                          ) -> ClientResponse | str | dict:
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


def test_proxies(proxies: list, url: str = 'icanhazip.com', enable_prints: bool = False, timeout=3):
    """ Sync call of test_proxies """
    return asyncio.run(async_test_proxies(proxies, url, enable_prints, timeout=timeout))


def scrap_free_proxies(enable_prints: bool = False):
    """ Sync call of scrap_free_proxies """
    return asyncio.run(async_scrap_free_proxies(enable_prints=enable_prints))


if __name__ == '__main__':
    from my import get_proxies_from_file
    # print(test_proxies(scrap_free_proxies(enable_prints=True), enable_prints=True))
    res = scrap_free_proxies(enable_prints=True)
    print(len(res), res)
    # test_proxies(proxies=res, enable_prints=True)
