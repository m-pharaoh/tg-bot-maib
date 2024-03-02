from web3 import Web3

# Replace these values with your actual contract details
# token_contract_address = "0xADd15b30E7B4f4408cdCc52999192901895c75A4"   # TESTNET
# bsc_testnet_node_url = "https://data-seed-prebsc-1-s1.binance.org:8545"

token_contract_address = "0xC218EF3Cc52D5D93b0eDEcf30Cdc2a98804cfeC5" 
bsc_mainnet_node_url = "https://bsc-dataseed1.binance.org/"

# Connect to the BSC Mainnet node
web3 = Web3(Web3.HTTPProvider(bsc_mainnet_node_url))

# Load the ERC-20 token contract ABI
token_contract_abi = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    }
]

# Create a contract object for the ERC-20 token
token_contract = web3.eth.contract(address=token_contract_address, abi=token_contract_abi)

def get_token_balance(user_wallet: str) -> int:
    try:
        # Call the 'balanceOf' function to get the token balance for the user's address
        result = Web3.from_wei(token_contract.functions.balanceOf(user_wallet).call(), 'ether')
        return result
    except Exception as e:
        return 0



access_amount = 75000 # 75,000 $MAIB tokens required to access email bot

def verify_access_for_email_bot(user_wallet: str) -> bool:
    return get_token_balance(user_wallet) >= access_amount
    