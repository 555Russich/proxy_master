import re
import json
import math
import time
import asyncio
import traceback
from pathlib import Path

from bs4 import BeautifulSoup
import pycountry
from aiohttp import (
    ClientSession,
    ClientResponse,
)
from aiohttp_socks import ProxyConnector

FILEPATH = Path(Path.home(), 'proxy_master').with_suffix('.json')
DO_PRINTS: bool = True
PATTERN_IP_PORT = re.compile(
    r"((([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5]):\d{1,5})"
)
# NOTE: settings should be changed here, not in json.
# Value is the time in minutes after update needed.
# Some sites don't provide this information, it's my choice
WEBSITES_WITH_PROXIES = {
    'free-proxy-list.net': 30,
    'geonode.com': 60 * 12,
    # 'openproxy.space': 60,  # host is not working from 16.02.2023-18.02.2023
    # 'freeproxylists.net': 30, # got 403
    'hidemy.name': 60 * 24 * 3
}
WEBSITES_TO_TEST_IP = [
    'icanhazip.com',
    '2ip.ru'
]


class DataHandler:
    @staticmethod
    def get_proxies_list(
            data: dict[dict],
            protocol: str = None,
            source: str = None
    ) -> list[str]:
        """
            Return list of proxies in format "IP:PORT" based on filters
        """

        proxies = []
        for domain, website_data in data.items():
            if source and source != domain:
                continue

            for proxy in website_data['proxies']:
                if not protocol:
                    proxies.append(f'{proxy["ip"]}:{proxy["port"]}')
                elif protocol and protocol in proxy['protocols']:
                    proxies.append(f'{proxy["ip"]}:{proxy["port"]}')

        return proxies


class Scrapper:
    @staticmethod
    async def send_request(
            url: str,
            response_type: str,
            proxy: str = None,
            connector: ProxyConnector = None,
            headers: dict = None,
            params: dict = None,
            json_: dict = None,
            timeout: int = 3
    ) -> str | dict | ClientResponse:
        """
            Send asynchronously request using one of aiohttp.ClientSession method
        """

        async with ClientSession(connector=connector) as session:
            async with session.get(
                    url=url,
                    proxy=proxy,
                    headers=headers,
                    json=json_,
                    params=params,
                    timeout=timeout
            ) as response:
                match response.status:
                    case 200:
                        match response_type:
                            case 'text':
                                return str(await response.text())
                            case 'json':
                                return await response.json()
                    case _:
                        return response

    @staticmethod
    async def test_public_ip(
            proxies: list,
            proxy_protocol: str,
            website_protocol: str,
            url: str = 'icanhazip.com',
            timeout: int = 3,
            do_prints: bool = DO_PRINTS,
    ) -> list:

        assert url in WEBSITES_TO_TEST_IP, \
            f'Unavailable to check ip address from {url}\n' \
            f'Use one of this websites: {WEBSITES_TO_TEST_IP}'

        working_proxies = []
        tasks = [
            asyncio.create_task(
                Scrapper.send_request(
                    response_type='text',
                    url=f'{website_protocol}://{url}',
                    proxy=f'{proxy_protocol}://{proxy}' if proxy_protocol in ('http', 'https') else None,
                    connector=ProxyConnector.from_url(f'{proxy_protocol}://{proxy}')
                    if proxy_protocol in ('socks4', 'socks5') else None,
                    timeout=timeout
                )
            ) for proxy in proxies
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for proxy, result in zip(proxies, results):
            if isinstance(result, str):
                match url:
                    case 'icanhazip.com':
                        public_ip = result.strip()
                    case '2ip.ru':
                        public_ip = BeautifulSoup(result, 'lxml').find('div', class_='ip', ).find('span').text
                    case _:
                        public_ip = None

                if public_ip == proxy.split(':')[0]:
                    print(f'Working! Proxy: {proxy}') if do_prints else ...
                    working_proxies.append(proxy)

        print(f'{len(working_proxies)}/{len(proxies)} proxies works') if do_prints else ...
        return working_proxies

    @staticmethod
    async def _scrap_website(
            domain: str,
            data: dict[dict],
            do_prints: bool = DO_PRINTS
    ) -> list[dict]:

        proxies = []
        match domain:
            case 'free-proxy-list.net':
                response: str = await Scrapper.send_request(
                    url=f'https://free-proxy-list.net',
                    response_type='text'
                )

                for tr in BeautifulSoup(response, 'lxml').table.tbody.find_all('tr'):
                    tds = tr.find_all('td')
                    proxy = {
                        'ip': tds[0].text,
                        'port': tds[1].text,
                        'protocols': ['https'] if tds[-2].text == 'yes' else ['http'],
                        'country': tds[2].text,
                        'anonymity': tds[4].text.replace(' proxy', ''),
                    }

                    last_checked_lst = tds[-1].text.split()
                    if last_checked_lst[1].startswith('sec'):
                        proxy['last_checked'] = int(time.time()) - int(last_checked_lst[0])
                    elif last_checked_lst[1].startswith('min'):
                        proxy['last_checked'] = int(time.time()) - int(last_checked_lst[0]) * 60
                    elif last_checked_lst[1].startswith('hour'):
                        proxy['last_checked'] = int(time.time()) - int(last_checked_lst[0]) * 3600
                    else:
                        print(f'Unexpected time metric in row: {tds[-1].text} | {domain=}') if do_prints else ...

                    proxies.append(proxy)
            case 'geonode.com':
                params = {
                    "limit": 1,
                    "page": 1,
                    "sort_by": "",
                    "sort_type": "",
                    "protocols": '',
                }
                response: dict = await Scrapper.send_request(
                    url='https://proxylist.geonode.com/api/proxy-list',
                    response_type='json',
                    params=params,
                )

                params['limit'] = 500
                for page in range(1, math.ceil(response['total'] / params['limit']) + 1):
                    count_before = len(proxies)

                    params['page'] = page
                    response: dict = await Scrapper.send_request(
                        url='https://proxylist.geonode.com/api/proxy-list',
                        response_type='json',
                        params=params,
                        timeout=20
                    )

                    data = response['data']
                    for proxy in data:
                        proxy_data = {
                            'ip': proxy['ip'],
                            'port': proxy['port'],
                            'protocols': proxy['protocols'],
                            'country': proxy['country'],
                            'anonymity': proxy['anonymityLevel'],
                            'last_checked': proxy['lastChecked']
                        }
                        proxies.append(proxy_data)
                    print(f'Scrapped {len(proxies) - count_before} proxies from page={params["page"]} {domain}') \
                        if do_prints else ...
            case 'openproxy.space':
                # https://openproxy.space/list/http
                # host is not working now ...
                raise NotImplementedError
            case 'freeproxylists.net':
                # 403 forbidden
                raise NotImplementedError
                # headers = {
                #     'authority': 'www.freeproxylists.net',
                #     'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
                #     'accept-language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                #     'cache-control': 'max-age=0',
                #     # 'cookie': 'hl=ru; userno=20230103-000706; from=google; refdomain=www.google.com; visited=2023%2F01%2F03%2002%3A38%3A58; pv=6',
                #     'origin': 'https://www.freeproxylists.net',
                #     'referer': 'https://www.freeproxylists.net/ru/',
                #     'sec-ch-ua': '"Not?A_Brand";v="8", "Chromium";v="108", "Google Chrome";v="108"',
                #     'sec-ch-ua-mobile': '?0',
                #     'sec-ch-ua-platform': '"Linux"',
                #     'sec-fetch-dest': 'document',
                #     'sec-fetch-mode': 'navigate',
                #     'sec-fetch-site': 'same-origin',
                #     'sec-fetch-user': '?1',
                #     'upgrade-insecure-requests': '1',
                #     'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
                # }
                #
                # last_page = None
                # params = {'page': 1}
                # while True:
                #     response = await self._send_request(
                #         url='https://www.freeproxylists.net/ru/',
                #         response_type='text',
                #         headers=headers,
                #         params=params,
                #         timeout=10
                #     )
                #     soup = BeautifulSoup(response, 'lxml')
                #     if not last_page:
                #         last_page = int(soup.find('div', class_='page').find_all('a')[-2].text)
                #
                #     count_before = len(proxies)
                #     for tr in soup.find('table', class_='DataGrid').find_all('tr')[1:]:
                #         try:
                #             ip_hex = str(tr.find_all('td')[0].string).replace('IPDecode', '')[2:-2]
                #             ip = BeautifulSoup(bytearray.fromhex(ip_hex.replace('%', '')).decode(), 'lxml').text
                #             port = tr.find_all('td')[1].text
                #             proxies.append(f'{ip}:{port}')
                #         except IndexError:
                #             continue
                #     count_after = len(proxies)
                #
                #     print(f'{domain=} | page={params["page"]} | proxies from page: {count_after - count_before} |'
                #           f'total: {len(proxies)}') if do_prints else None
                #
                #     if params['page'] == last_page:
                #         break
                #     params['page'] += 1
            case 'hidemy.name':
                headers = {
                    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,"
                              "image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
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
                    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                                  "Chrome/107.0.0.0 Safari/537.36"
                }

                proxies_to_scrap = DataHandler.get_proxies_list(data, 'socks4')
                # making request to get pagination
                response = await Scrapper.send_request(
                    url=f'https://hidemy.name/en/proxy-list/',
                    response_type='text',
                    headers=headers,
                    timeout=3
                )
                if isinstance(response, ClientResponse) and response.status == 403:
                    while isinstance(response, ClientResponse):
                        tasks = []
                        for proxy in proxies_to_scrap:
                            task = asyncio.create_task(
                                Scrapper.send_request(
                                    url=f'https://hidemy.name/en/proxy-list/',
                                    response_type='text',
                                    connector=ProxyConnector.from_url(f'socks4://{proxy}'),
                                    headers=headers,
                                    timeout=5
                                )
                            )
                            tasks.append(task)
                        for result in await asyncio.gather(*tasks):
                            if isinstance(result, str):
                                response = result
                                break

                last_pagination = int(BeautifulSoup(response, 'lxml').
                                      find('div', class_='pagination').find_all('li')[-2].text)

                pages = [x for x in range(last_pagination + 1)]

                while pages:
                    pages_to_tasks = pages * (len(proxies_to_scrap) // len(pages))
                    pages_to_tasks += pages[:len(proxies_to_scrap) - len(pages_to_tasks)]
                    tasks = []

                    for proxy, page in zip(proxies_to_scrap, pages_to_tasks):
                        tasks.append(
                            asyncio.create_task(
                                Scrapper.send_request(
                                    url=f'https://hidemy.name/en/proxy-list/',
                                    response_type='text',
                                    connector=ProxyConnector.from_url(f'socks4://{proxy}'),
                                    headers=headers,
                                    params={'start': page * 64},
                                    timeout=10
                                )
                            )
                        )

                    for result, page in zip(await asyncio.gather(*tasks, return_exceptions=True), pages_to_tasks):
                        if page not in pages:
                            continue
                        if isinstance(result, str):
                            soup = BeautifulSoup(result, 'lxml')

                            for tr in soup.table.tbody.find_all('tr'):
                                tds = tr.find_all('td')
                                proxy_data = {
                                    'ip': tds[0].text,
                                    'port': tds[1].text,
                                    'protocols': [x.lower().strip() for x in tds[4].text.split(',')],
                                    'country': ...,
                                    'anonymity': ...,
                                    'last_checked': ...,
                                }

                                match tds[2].find('span', class_='country').text.strip().lower():
                                    case 'kazakstan':
                                        country_code = 'KZ'
                                    case unhandled:
                                        try:
                                            country_code = pycountry.countries.search_fuzzy(unhandled)[0] \
                                                .alpha_2
                                        except LookupError:
                                            country_code = None
                                proxy_data['country'] = country_code

                                match tds[-2].text.lower():
                                    case 'no':
                                        proxy_data['anonymity'] = 'transparent'
                                    case 'low' | 'average':
                                        proxy_data['anonymity'] = 'anonymous'
                                    case 'high':
                                        proxy_data['anonymity'] = 'elite'
                                    case _:
                                        print(f'Unexpected anonymity type in row: {tds[-2].text} |'
                                              f' {domain=}') if do_prints else ...

                                match tds[-1].text.split():
                                    case n_seconds, 'seconds':
                                        proxy_data['last_checked'] = int(time.time()) - (int(n_seconds))
                                    case n_minutes, 'minutes':
                                        proxy_data['last_checked'] = int(time.time()) - (int(n_minutes) * 60)
                                    case n_hours, 'h.', n_minutes, 'min.':
                                        proxy_data['last_checked'] = \
                                            int(time.time() - (int(n_hours) * 3600 + int(n_minutes) * 60))
                                    case _:
                                        print(f'Unexpected time metric in row: {tds[-1].text} |'
                                              f' {domain=}') if do_prints else ...
                                proxies.append(proxy_data)

                            # previous_href = soup.find('li', class_='prev_array').a.get('href')
                            # if '/en/proxy-list/#list' in previous_href:
                            #     current_page = 0
                            # else:
                            #     current_page = int(re.search(r'\d+(?=#list)', previous_href).group(0)) // 64 + 1

                            # print(f'{current_page=}')
                            # for page_ in pages:
                            #     pages.remove(current_page)

                            pages.remove(page)
                            print(f'Scrapped {len(proxies)} proxies | pages left: {len(pages)} |'
                                  f' {domain}') if do_prints else ...
        return proxies

    @staticmethod
    async def scrap_or_read(do_prints: bool = DO_PRINTS) -> dict[dict]:
        """
            Check for each domain if update requires, run scrapper or keep existing proxies from json.
            If file does not exist, create empty dict based on WEBSITES_WITH_PROXIES.
        """

        if FILEPATH.exists():
            with open(FILEPATH, 'r') as f:
                data = json.load(f)
        else:
            data = {}

        for domain, update_after_min in WEBSITES_WITH_PROXIES.items():
            if not data.get(domain):
                data[domain] = {
                    'update_after_min': update_after_min,
                    'last_update': int(time.time() - (update_after_min + 1) * 60),
                    'proxies': []
                }
            # overwrite update_after_min in json
            elif data.get(domain) and data[domain]['update_after_min'] != update_after_min:
                data[domain]['update_after_min'] = update_after_min

        anyone_updated = False
        for domain, website_data in data.items():
            if (time.time() - website_data['last_update']) // 60 > website_data['update_after_min']:
                try:
                    website_data['proxies'] = await Scrapper._scrap_website(domain, data)
                    website_data['last_update'] = int(time.time())
                    anyone_updated = True
                    print(f'Scrapped {len(website_data["proxies"])} proxies from {domain}') if do_prints else ...
                except NotImplementedError:
                    pass
                except Exception:
                    print(f'Error while scrapping proxies from {domain}\n'
                          f'{traceback.format_exc()}') if do_prints else ...

        if anyone_updated:
            with open(FILEPATH, 'w') as f:
                json.dump(data, f, indent=4)

        return data


def get_proxies(
        protocol: str = None,
        source: str = None,
        do_prints: bool = DO_PRINTS,
) -> list[str]:
    """
        High level function for import in other synchronous project
    """

    return DataHandler.get_proxies_list(
        asyncio.run(
            Scrapper.scrap_or_read(do_prints=do_prints)
        ),
        protocol=protocol,
        source=source
    )


def test_proxies(
        proxies: list[str],
        proxy_protocol: str,
        website_protocol: str,
        url: str = WEBSITES_TO_TEST_IP[0],
        timeout: int = 3,
        do_prints: bool = DO_PRINTS
) -> list[str]:
    """
        High level function for testing proxies in other synchronous project
    """

    return asyncio.run(
        Scrapper.test_public_ip(
            proxies=proxies,
            proxy_protocol=proxy_protocol,
            website_protocol=website_protocol,
            url=url,
            timeout=timeout,
            do_prints=do_prints
        )
    )


async def async_main():
    """ TEST """
    data = await Scrapper.scrap_or_read()
    proxies = DataHandler.get_proxies_list(data, protocol='https')
    print(len(proxies))


def main():
    """ TEST """
    proxies = get_proxies(protocol='socks5')
    print(len(proxies))
    # print(proxies)


""" FOR TESTING"""
if __name__ == '__main__':
    main()
