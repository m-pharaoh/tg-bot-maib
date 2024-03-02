from web3 import Web3

# contract_address = "0xE0F898Aefb5f1E231f111CF4c1288D571bCb7195" # TESTNET
# bsc_testnet_node_url = "https://data-seed-prebsc-1-s1.binance.org:8545"

verify_wallet_contract_address = "0x452ABc53dC3dFAac477A1D8811Da2fd14FF2FBd2" 
bsc_mainnet_node_url = "https://bsc-dataseed1.binance.org/"

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

# Connect to the BSC Mainnet node
web3 = Web3(Web3.HTTPProvider(bsc_mainnet_node_url))

# CONTRACT
verify_contract = web3.eth.contract(address=verify_wallet_contract_address, abi=contract_abi)

def verify_user_wallet(user_wallet: str, encrypted_username: str) -> bool:
    try:
        result = verify_contract.functions.userWallets(user_wallet).call()
        return result == encrypted_username
    except:
        return False
