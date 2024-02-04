from web3 import Web3

contract_address = "0xE0F898Aefb5f1E231f111CF4c1288D571bCb7195" # TESTNET

contract_abi = [
    {
        "inputs": [
            {
                "internalType": "string",
                "name": "_accessCode",
                "type": "string"
            }
        ],
        "name": "setWalletToAccessCode",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {
                "internalType": "address",
                "name": "",
                "type": "address"
            }
        ],
        "name": "userWallets",
        "outputs": [
            {
                "internalType": "string",
                "name": "",
                "type": "string"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    }
]

bsc_testnet_node_url = "https://data-seed-prebsc-1-s1.binance.org:8545"

# Connect to the BSC Testnet node
web3 = Web3(Web3.HTTPProvider(bsc_testnet_node_url))

# CONTRACT
verify_contract = web3.eth.contract(address=contract_address, abi=contract_abi)

def verify_user_wallet(user_wallet: str, encrypted_username: str) -> bool:
    try:
        result = verify_contract.functions.userWallets(user_wallet).call()
        return result == encrypted_username
    except:
        return False
