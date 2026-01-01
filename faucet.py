import requests
import time
import json
from eth_account import Account
from colorama import Fore, Style, init
import sys
import threading
from queue import Queue

init(autoreset=True)

class PolariseFaucet:
    def __init__(self):
        self.api_url = "https://apifaucet-t.polarise.org/claim"
        self.recaptcha_site_key = "6Le97hIsAAAAAFsmmcgy66F9YbLnwgnWBILrMuqn"
        self.recaptcha_url = "https://faucet.polarise.org/"
        self.accounts = []
        self.captcha_keys = []
        self.proxies = []
        self.current_proxy_index = 0
        self.use_proxy = True
        self.lock = threading.Lock()
        self.total_success = 0
        self.total_failed = 0

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
            print(f"{Fore.GREEN}✓ Loaded captcha key")
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
        print(f"{Fore.CYAN}⏳ Solving reCAPTCHA...")
        
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
                time.sleep(2)
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
            
            print(f"{Fore.CYAN}[Round {round_number}][Account #{account_number}] ⏳ Claiming for address: {address}")
            
            headers = {
                'accept': 'application/json, text/plain, */*',
                'accept-language': 'id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7',
                'content-type': 'application/json',
                'origin': 'https://faucet.polarise.org',
                'referer': 'https://faucet.polarise.org/',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-site',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36'
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
                try:
                    result = response.json()
                    if result.get('code') == 200:
                        amount = result.get('amount', '0')
                        txhash = result.get('txhash', '')
                        
                        print(f"{Fore.GREEN}[Round {round_number}][Account #{account_number}] ✓ Claim successful for {address}!")
                        print(f"{Fore.GREEN}[Round {round_number}][Account #{account_number}]   Amount: {amount} POLAR")
                        print(f"{Fore.GREEN}[Round {round_number}][Account #{account_number}]   TxHash: {txhash}")
                        print(f"{Fore.CYAN}[Round {round_number}][Account #{account_number}]   Explorer: https://explorer.polarise.org/tx/{txhash}")
                        return True
                    else:
                        print(f"{Fore.RED}[Round {round_number}][Account #{account_number}] ✗ Claim failed: {response.text}")
                        return False
                except json.JSONDecodeError:
                    print(f"{Fore.GREEN}[Round {round_number}][Account #{account_number}] ✓ Claim successful!")
                    print(f"{Fore.GREEN}[Round {round_number}][Account #{account_number}] Response: {response.text}")
                    return True
            else:
                print(f"{Fore.RED}[Round {round_number}][Account #{account_number}] ✗ Claim failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}[Round {round_number}][Account #{account_number}] ✗ Error claiming faucet: {str(e)}")
            return False
    
    def worker(self, queue, captcha_solution, round_number=1):
        while True:
            item = queue.get()
            if item is None:
                break
            
            idx, private_key = item
            
            print(f"{Fore.YELLOW}[Round {round_number}][Account #{idx}] {'-'*40}")
            print(f"{Fore.YELLOW}[Round {round_number}][Account #{idx}] Processing account {idx}/{len(self.accounts)}")
            print(f"{Fore.YELLOW}[Round {round_number}][Account #{idx}] {'-'*40}")
            
            proxy = self.get_next_proxy()
            
            if self.claim_faucet(private_key, captcha_solution, proxy, idx, round_number):
                with self.lock:
                    self.total_success += 1
            else:
                with self.lock:
                    self.total_failed += 1
            
            queue.task_done()
    
    def process_round(self, round_number, batch_size, captcha_solution):
        """Process one round of claims for all accounts"""
        print(f"\n{Fore.MAGENTA}{'='*60}")
        print(f"{Fore.MAGENTA}ROUND {round_number} - Starting claims...")
        print(f"{Fore.MAGENTA}{'='*60}\n")
        
        round_success = 0
        round_failed = 0
        
        queue = Queue()
        threads = []
        
        for i in range(batch_size):
            t = threading.Thread(target=self.worker, args=(queue, captcha_solution, round_number))
            t.start()
            threads.append(t)
        
        for idx, private_key in enumerate(self.accounts, 1):
            queue.put((idx, private_key))
        
        queue.join()
        
        for i in range(batch_size):
            queue.put(None)
        for t in threads:
            t.join()
        
        with self.lock:
            round_success = self.total_success
            round_failed = self.total_failed
        
        print(f"\n{Fore.MAGENTA}{'='*60}")
        print(f"{Fore.MAGENTA}ROUND {round_number} - Completed!")
        print(f"{Fore.MAGENTA}{'='*60}")
        print(f"{Fore.GREEN}Success: {round_success}")
        print(f"{Fore.RED}Failed: {round_failed}")
        print(f"{Fore.CYAN}Total: {len(self.accounts)}")
        print(f"{Fore.MAGENTA}{'='*60}")
        
        return round_success, round_failed
    
    def run(self):
        print(f"{Fore.CYAN}{'='*60}")
        print(f"{Fore.CYAN}Polarise Faucet Auto Claim Bot (Multi-threaded)")
        print(f"{Fore.CYAN}{'='*60}\n")
        
        self.load_accounts()
        self.load_captcha_keys()
        self.load_proxies()
        
        if not self.accounts or not self.captcha_keys:
            print(f"{Fore.RED}✗ Missing required configuration files!")
            return
        
        if self.proxies:
            choice = input(f"\n{Fore.YELLOW}Use proxy rotation? (y/n): ").lower()
            self.use_proxy = choice == 'y'
        
        while True:
            try:
                batch_size = int(input(f"\n{Fore.YELLOW}Enter number of concurrent accounts (batch size): "))
                if batch_size > 0 and batch_size <= len(self.accounts):
                    break
                else:
                    print(f"{Fore.RED}✗ Please enter a number between 1 and {len(self.accounts)}")
            except ValueError:
                print(f"{Fore.RED}✗ Please enter a valid number")
        
        while True:
            try:
                total_rounds = int(input(f"{Fore.YELLOW}Enter number of claim rounds (how many times to process all accounts): "))
                if total_rounds > 0:
                    break
                else:
                    print(f"{Fore.RED}✗ Please enter a number greater than 0")
            except ValueError:
                print(f"{Fore.RED}✗ Please enter a valid number")
        
        print(f"\n{Fore.CYAN}{'='*60}")
        print(f"{Fore.CYAN}Configuration:")
        print(f"{Fore.CYAN}  - Total Accounts: {len(self.accounts)}")
        print(f"{Fore.CYAN}  - Concurrent Threads: {batch_size}")
        print(f"{Fore.CYAN}  - Total Rounds: {total_rounds}")
        print(f"{Fore.CYAN}  - Delay Between Rounds: 30 seconds")
        print(f"{Fore.CYAN}  - Captcha Refresh: Every 3 rounds")
        print(f"{Fore.CYAN}{'='*60}\n")
        
        print(f"{Fore.CYAN}Solving initial captcha...")
        captcha_solution = self.solve_recaptcha(self.captcha_keys)
        if not captcha_solution:
            return
        
        all_rounds_stats = []
        
        for round_num in range(1, total_rounds + 1):
            if round_num > 1 and (round_num - 1) % 3 == 0:
                print(f"\n{Fore.MAGENTA}{'='*60}")
                print(f"{Fore.MAGENTA}🔄 Refreshing captcha (every 3 rounds)...")
                print(f"{Fore.MAGENTA}{'='*60}\n")
                captcha_solution = self.solve_recaptcha(self.captcha_keys)
                if not captcha_solution:
                    print(f"{Fore.RED}✗ Failed to refresh captcha, stopping...")
                    break
            
            self.total_success = 0
            self.total_failed = 0
            
            success, failed = self.process_round(round_num, batch_size, captcha_solution)
            all_rounds_stats.append((round_num, success, failed))
            
            if round_num < total_rounds:
                print(f"\n{Fore.YELLOW}⏳ Waiting 30 seconds before next round...")
                for remaining in range(30, 0, -1):
                    print(f"{Fore.YELLOW}   {remaining} seconds remaining...", end='\r')
                    time.sleep(1)
                print(f"{Fore.GREEN}   Ready to start next round!     ")
        
        print(f"\n{Fore.CYAN}{'='*60}")
        print(f"{Fore.CYAN}ALL ROUNDS COMPLETED!")
        print(f"{Fore.CYAN}{'='*60}\n")
        
        total_success_all = 0
        total_failed_all = 0
        
        print(f"{Fore.CYAN}Summary by Round:")
        for round_num, success, failed in all_rounds_stats:
            print(f"{Fore.YELLOW}  Round {round_num}: {Fore.GREEN}Success: {success} {Fore.RED}Failed: {failed}")
            total_success_all += success
            total_failed_all += failed
        
        print(f"\n{Fore.CYAN}{'='*60}")
        print(f"{Fore.GREEN}Total Success (All Rounds): {total_success_all}")
        print(f"{Fore.RED}Total Failed (All Rounds): {total_failed_all}")
        print(f"{Fore.CYAN}Total Claims Attempted: {total_success_all + total_failed_all}")
        print(f"{Fore.CYAN}{'='*60}")

if __name__ == "__main__":
    bot = PolariseFaucet()
    bot.run()