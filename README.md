This module provide asynchronously scrapping a bunch of `http`, `https`, `socks4`, `socks5` proxies from websites such as:
1) [free-proxy-list.net](https://free-proxy-list.net)
2) [geonode.com](https://geonode.com)
3) [hidemy.name](https://hidemy.name)

Just now proxy-master scrapped `23265 proxies` from websites above. Count of unique by ip:port is `18383`, 
but some servers support different protocols.

> I add more websites to scrap from time to time, **BUT** looking for help and advices 
from people with experience

## Dependencies 

`python3.10` and higher. Pattern matching using in project

<sub>Will be installed automatically with `pip`</sub>

[aiohttp](https://github.com/aio-libs/aiohttp)
[bs4](https://pypi.org/project/beautifulsoup4/)
[lxml](https://pypi.org/project/lxml/)
[pycountry](https://github.com/flyingcircusio/pycountry)
[aiohttp_socks](https://github.com/romis2012/aiohttp-socks)

## Installation
`pip install proxy-master`

## Usage

1. This will create `proxy_master.json` in you home directory and return list of proxies.
```python
import proxy_master as pm
proxies = pm.get_proxies(
    protocol='http',
    do_prints=True
)
```
Then you can test proxies:
```python
working_proxies = pm.test_proxies(
    proxies,
    proxy_protocol: 'http',
    website_protocol: 'http'
)
```

## Features
- [x] Scrap different type of proxies include `https`, `socks4`, `socks5`
- [x] <i>Recursively</i> scrapping. Use already collected proxies to scrap another website
- [x] test_public_ip(...) `socks4`, `socks5` using <a href="https://github.com/Skactor/aiohttp-proxy">aiohttp-proxy</a>

## In plans
- [] https://freeproxylists.net
- [] https://spys.one/en/free-proxy-list/
- 