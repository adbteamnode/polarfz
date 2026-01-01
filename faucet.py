import requests
import time
import json
from eth_account import Account
from colorama import Fore, Style, init
import sys
import threading
from queue import Queue

# Colorama ကို အသုံးပြုဖို့ Initialize လုပ်ခြင်း
init(autoreset=True)

class PolariseFaucet:
    def __init__(self):
        self.api_url = "https://apifaucet-t.polarise.org/claim"
        self.recaptcha_site_key = "6Le97hIsAAAAAFsmmcgy66F9YbLnwgnWBILrMuqn"
        self.recaptcha_url = "https://faucet.polarise.org/"
        self.accounts = []
        self.captcha_keys = ""
        self.proxies = []
        self.current_proxy_index = 0
        self.use_proxy = True
        self.lock = threading.Lock()
        self.total_success = 0
        self.total_failed = 0

    def welcome(self):
        # ASCII Art Logo ကို အရောင်များဖြင့် ဖော်ပြခြင်း
        print(f"""{Fore.CYAN}{Style.BRIGHT}
       █████╗ ██████╗ ██████╗     ███╗   ██╗ ██████╗ ██████╗ ███████╗
      ██╔══██╗██╔══██╗██╔══██╗    ████╗  ██║██╔═══██╗██╔══██╗██╔════╝
      ███████║██║  ██║██████╔╝    ██╔██╗ ██║██║   ██║██║  ██║█████╗  
      ██╔══██║██║  ██║██╔══██╗    ██║╚██╗██║██║   ██║██║  ██║██╔══╝  
      ██║  ██║██████╔╝██████╔╝    ██║ ╚████║╚██████╔╝██████╔╝███████╗
      ╚═╝  ╚═╝╚═════╝ ╚═════╝     ╚═╝  ╚═══╝ ╚═════╝ ╚═════╝ ╚══════╝
        {Fore.WHITE}By : ADB NODE
        {Fore.GREEN + Style.BRIGHT}Auto Faucet {Fore.BLUE + Style.BRIGHT}polarise faucet
        {Fore.GREEN + Style.BRIGHT}ADBNODE? {Fore.YELLOW + Style.BRIGHT}<Modified Script>
        """)

    def load_accounts(self, filename='wallets.txt'):
        try:
            with open(filename, 'r') as f:
                self.accounts = [line.strip() for line in f if line.strip()]
            print(f"{Fore.GREEN}✓ Loaded {len(self.accounts)} accounts")
        except FileNotFoundError:
            print(f"{Fore.RED}✗ {filename} not found!")
            sys.exit(1)
    
    def load_captcha_keys(self, filename='captcha_key.txt'):
        try:
            with open(filename, 'r') as f:
                self.captcha_keys = f.readline().strip()
            if self.captcha_keys:
                print(f"{Fore.GREEN}✓ Loaded captcha key")
            else:
                print(f"{Fore.RED}✗ Captcha key file is empty!")
                sys.exit(1)
        except FileNotFoundError:
            print(f"{Fore.RED}✗ {filename} not found!")
            sys.exit(1)
    
    def load_proxies(self, filename='proxy.txt'):
        try:
            with open(filename, 'r') as f:
                self.proxies = [line.strip() for line in f if line.strip()]
            if self.proxies:
                print(f"{Fore.GREEN}✓ Loaded {len(self.proxies)} proxies")
            else:
                print(f"{Fore.YELLOW}⚠ No proxies found, will use direct connection")
                self.use_proxy = False
        except FileNotFoundError:
            print(f"{Fore.YELLOW}⚠ {filename} not found, will use direct connection")
            self.use_proxy = False
    
    def get_next_proxy(self):
        if not self.use_proxy or not self.proxies:
            return None
        
        with self.lock:
            proxy = self.proxies[self.current_proxy_index]
            self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
        
        if proxy.startswith('http://') or proxy.startswith('https://'):
            return {'http': proxy, 'https': proxy}
        else:
            return {'http': f'http://{proxy}', 'https': f'http://{proxy}'}
    
    def solve_recaptcha(self, api_key):
        print(f"{Fore.CYAN}⏳ Solving reCAPTCHA via 2Captcha...")
        
        submit_url = "http://2captcha.com/in.php"
        params = {
            'key': api_key,
            'method': 'userrecaptcha',
            'googlekey': self.recaptcha_site_key,
            'pageurl': self.recaptcha_url,
            'json': 1
        }
        
        try:
            response = requests.post(submit_url, data=params, timeout=30)
            result = response.json()
            
            if result.get('status') != 1:
                print(f"{Fore.RED}✗ Failed to submit captcha: {result.get('request')}")
                return None
            
            captcha_id = result.get('request')
            print(f"{Fore.YELLOW}⏳ Captcha ID: {captcha_id}, waiting for solution...")
            
            result_url = "http://2captcha.com/res.php"
            for i in range(60):
                time.sleep(5)
                params = {
                    'key': api_key,
                    'action': 'get',
                    'id': captcha_id,
                    'json': 1
                }
                
                response = requests.get(result_url, params=params, timeout=30)
                result = response.json()
                
                if result.get('status') == 1:
                    captcha_solution = result.get('request')
                    print(f"{Fore.GREEN}✓ Captcha solved!")
                    return captcha_solution
                elif result.get('request') != 'CAPCHA_NOT_READY':
                    print(f"{Fore.RED}✗ Captcha error: {result.get('request')}")
                    return None
            
            print(f"{Fore.RED}✗ Captcha timeout")
            return None
            
        except Exception as e:
            print(f"{Fore.RED}✗ Error solving captcha: {str(e)}")
            return None
    
    def claim_faucet(self, private_key, captcha_solution, proxy, account_number, round_number=1):
        try:
            account = Account.from_key(private_key)
            address = account.address
            
            headers = {
                'accept': 'application/json, text/plain, */*',
                'content-type': 'application/json',
                'origin': 'https://faucet.polarise.org',
                'referer': 'https://faucet.polarise.org/',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            payload = {
                "address": address,
                "denom": "uluna",
                "response": captcha_solution
            }
            
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                proxies=proxy,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 200:
                    txhash = result.get('txhash', 'No Hash')
                    print(f"{Fore.GREEN}[Round {round_number}][Account #{account_number}] ✓ Success: {address} | Tx: {txhash}")
                    return True
                else:
                    print(f"{Fore.RED}[Round {round_number}][Account #{account_number}] ✗ Failed: {result.get('message', response.text)}")
                    return False
            else:
                print(f"{Fore.RED}[Round {round_number}][Account #{account_number}] ✗ HTTP {response.status_code}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}[Round {round_number}][Account #{account_number}] ✗ Error: {str(e)}")
            return False
    
    def worker(self, queue, captcha_solution, round_number=1):
        while True:
            item = queue.get()
            if item is None: break
            idx, private_key = item
            proxy = self.get_next_proxy()
            if self.claim_faucet(private_key, captcha_solution, proxy, idx, round_number):
                with self.lock: self.total_success += 1
            else:
                with self.lock: self.total_failed += 1
            queue.task_done()

    def process_round(self, round_number, batch_size, captcha_solution):
        print(f"\n{Fore.MAGENTA}--- ROUND {round_number} STARTING ---")
        queue = Queue()
        threads = []
        for i in range(batch_size):
            t = threading.Thread(target=self.worker, args=(queue, captcha_solution, round_number))
            t.start()
            threads.append(t)
        
        for idx, private_key in enumerate(self.accounts, 1):
            queue.put((idx, private_key))
        
        queue.join()
        for i in range(batch_size): queue.put(None)
        for t in threads: t.join()
        return self.total_success, self.total_failed

    def run(self):
        self.welcome()
        self.load_accounts()
        self.load_captcha_keys()
        self.load_proxies()
        
        if self.proxies:
            self.use_proxy = input(f"\n{Fore.YELLOW}Use proxy? (y/n): ").lower() == 'y'

        batch_size = int(input(f"{Fore.YELLOW}Concurrent threads: "))
        total_rounds = int(input(f"{Fore.YELLOW}Total rounds: "))
        
        captcha_solution = self.solve_recaptcha(self.captcha_keys)
        if not captcha_solution: return

        for round_num in range(1, total_rounds + 1):
            if round_num > 1 and (round_num - 1) % 3 == 0:
                captcha_solution = self.solve_recaptcha(self.captcha_keys)
            
            self.total_success = 0
            self.total_failed = 0
            self.process_round(round_num, batch_size, captcha_solution)
            
            if round_num < total_rounds:
                print(f"\n{Fore.YELLOW}Waiting 30s for next round...")
                time.sleep(30)

if __name__ == "__main__":
    bot = PolariseFaucet()
    bot.run()
