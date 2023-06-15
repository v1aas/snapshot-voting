from web3 import Web3
from eth_account.messages import encode_structured_data
from fake_useragent import UserAgent
from termcolor import colored
import requests
import time
import datetime
import random
import logging

ETH_RPC = 'https://eth.llamarpc.com'
web3 = Web3(Web3.HTTPProvider(ETH_RPC))
space = "stgdao.eth" # ПОМЕНЯТЬ СТРОКУ, ЕСЛИ ГОЛОСОВАНИЕ НЕ STARGATE

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter('%(levelname)s:%(asctime)s:%(message)s', datefmt='%H:%M:%S')
ch.setFormatter(formatter)
logger.addHandler(ch)

class Proposal:
    def __init__(self, proposal_id, description, start, end):
        self.id = proposal_id
        self.description = description
        self.start = start
        self.end = end
        self.choices = {}

    def add_choice(self, choice_id, choice_description):
        self.choices[choice_id] = choice_description

    def get_choices(self):
        return self.choices
    
    def __str__(self):
        return f" Голосование: {self.id} \n Описание: {self.description} \n Начало: {self.start} \n Конец: {self.end} \n Варианты: {self.choices} \n" 

def create_proposals_list(data_json):
    proposals = []
    for i in data_json:
        proposal = Proposal (
            proposal_id = i['id'],
            description = i['title'],
            start = datetime.datetime.fromtimestamp(i['start'], tz = datetime.timezone.utc).astimezone(),
            end = datetime.datetime.fromtimestamp(i['end'], tz = datetime.timezone.utc).astimezone()
        )
        for j, nubmer in enumerate(i['choices'], start=1):
            proposal.add_choice(nubmer, j)
        print(proposal)
        proposals.append(proposal)
    return proposals

def get_active_proposals(space):
    url = 'https://hub.snapshot.org/graphql'
    query = """ query Proposals {
        proposals(where: {space_in: "%s", state: "active"}, orderBy: "created", orderDirection: desc) {
            id
            title
            choices
            start
            end
            app
        }
    }
    """ % space
    response = requests.post(url, json={'query':query})
    try:
        response.raise_for_status()
        print(colored(f'Голосования получены успешны!', 'light_green'))
    except requests.exceptions.HTTPError as error:
        print(colored('Запрос вернул ошибку:'))
        print(error) 
    proposals = response.json()['data']['proposals']
    print(f'Найдены следующие голосования для {space}: ')
    return create_proposals_list(proposals)

def post_vote(account, space, proposal_id, choice):
    sig_signature = {
            "domain": {
                "name": "snapshot",
                "version": "0.1.4"
            },
            "types": {
                "Vote": [
                    {
                        "name": "from",
                        "type": "address"
                    },
                    {
                        "name": "space",
                        "type": "string"
                    },
                    {
                        "name": "timestamp",
                        "type": "uint64"
                    },
                    {
                        "name": "proposal",
                        "type": "bytes32"
                    },
                    {
                        "name": "choice",
                        "type": 'uint32'
                    },
                    {
                        "name": "reason",
                        "type": "string"
                    },
                    {
                        "name": "app",
                        "type": "string"
                    },
                    {
                        "name": "metadata",
                        "type": "string"
                    }
                ],
                'EIP712Domain': [{'name': 'name', 'type': 'string'}, {'name': 'version', 'type': 'string'}]
            },
            'primaryType': "Vote",
            "message": {
                "space": space,
                "proposal": Web3.to_bytes(hexstr=proposal_id),
                "choice": choice,
                "app": "snapshot",
                "reason": "",
                "from": account.address,
                "timestamp": int(time.time()),
                'metadata': "{}"
            }
        }
    # Sign the message
    signed_message = account.sign_message(encode_structured_data(primitive=sig_signature))
    data = get_data(account, signed_message, space, proposal_id, choice)
    post_request(data)
   
def post_request(data):
    headers = {'accept': 'application/json',
    'user-agent': 'Mozilla/5.0 (Windows NT 6.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.54 Safari/537.36'}
    response = requests.post('https://seq.snapshot.org/', json=data,
                    #  proxies={'http': proxy, 'https': proxy},
                    headers=headers)
    
    if response.status_code == 200:
        print(colored('Голосование успешно', 'light_green'))
    else:
        print(colored(f'Ошибка: {response.status_code}', 'light_red'))
        try:
            print(response.json())
        except ValueError:
            print(response.text)

def get_data(account, signed_message, space, proposal_id, choice):
    data = {
        "address": account.address,
        "sig": signed_message.signature.hex(),
        "data": {
            "domain": {
                "name": "snapshot",
                "version": "0.1.4"
            },
            "types": {
                "Vote": [{
                    "name": "from",
                    "type": "address"
                },
                    {
                        "name": "space",
                        "type": "string"
                    },
                    {
                        "name": "timestamp",
                        "type": "uint64"
                    },
                    {
                        "name": "proposal",
                        "type": "bytes32"
                    },
                    {
                        "name": "choice",
                        "type": 'uint32'
                    },
                    {
                        "name": "reason",
                        "type": "string"
                    },
                    {
                        "name": "app",
                        "type": "string"
                    },
                    {
                        "name": "metadata",
                        "type": "string"
                    }
                ]
            },
            "message": {
                "space": space,
                "proposal": proposal_id,
                "choice": choice,
                "app": "snapshot",
                "reason": "",
                "from": account.address,
                "timestamp": int(time.time()),
                'metadata': "{}"
            }
        }
    }
    return data

def get_private_keys():
    with open('private_keys.txt', 'r') as file:
        return [line.strip() for line in file.readlines()]

def main():
    private_keys = get_private_keys()
    proposals = get_active_proposals(space)
    for prop in proposals:
        for number, key in enumerate(private_keys, start=1):
            account = web3.eth.account.from_key(key)
            choice = random.choice(list(prop.get_choices().values()))
            logger.info(f'{number}/{len(private_keys)} Голосую кошельком {account.address} в {prop.id} за {choice} выбор')
            post_vote(account, space, prop.id, choice)
            sleep = random.randint(30,60) # ЗАДЕРЖКА МЕЖДУ АККАУНТАМИ
            logger.info(f'Сплю перед следующим кошельком {sleep} сек.')
            time.sleep(sleep)
    print(colored('Скрипт закончил работу', "light_green"))

if __name__ == "__main__":
    main()