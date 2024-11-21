import asyncio
import random
import ssl
import json
import time
import uuid
import requests
import shutil
from loguru import logger
from websockets_proxy import Proxy, proxy_connect
from fake_useragent import UserAgent
from itertools import product
import threading
from concurrent.futures import ThreadPoolExecutor

user_agent = UserAgent(os='windows', platforms='pc', browsers='chrome')
random_user_agent = user_agent.random

# Konstanta untuk multiple instance
INSTANCES_PER_PROXY = 10  # Optimal instance per proxy
MAX_CONCURRENT_TASKS = 300  # Sesuaikan dengan jumlah instance
ROTATION_INTERVAL = 90  # Percepat rotasi
MIN_TASK_INTERVAL = 5  # Interval minimal task
MAX_TASK_INTERVAL = 15  # Interval maksimal task
MULTIPLIER = 2.00  # Desktop App multiplier
TASK_SUCCESS_RATE = 0.98  # Tingkat keberhasilan task yang tinggi

class ProxyInstance:
    def __init__(self, proxy_url: str, instance_id: int):
        self.proxy_url = proxy_url
        self.instance_id = instance_id
        self.device_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{proxy_url}-{instance_id}"))
        self.hardware_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{proxy_url}-hw-{instance_id}"))
        self.installation_id = str(uuid.uuid4())
        self.last_rotation = time.time()
        self.last_task = time.time()
        self.success_count = 0
        self.error_count = 0
        # Tambahkan delay unik per instance
        self.task_delay = random.uniform(MIN_TASK_INTERVAL, MAX_TASK_INTERVAL)
        self.earnings = 0
        self.tasks_completed = 0
        self.last_task_time = time.time()
        
    async def optimize_task_response(self, task_data):
        """Optimasi response untuk maksimal point dengan multiplier 2.00x"""
        return {
            "id": task_data["id"],
            "origin_action": "TASK",
            "result": {
                "status": "success",
                "task_id": task_data.get("task_id"),
                "timestamp": int(time.time()),
                "completed": True,
                "error": None,
                # Parameter optimal untuk point maksimal
                "duration": random.randint(400, 800),  # Durasi sangat cepat
                "bandwidth_used": random.randint(2048*1024, 4096*1024),  # Bandwidth sangat tinggi
                "connection_quality": random.uniform(0.98, 0.999),  # Koneksi hampir sempurna
                "network_latency": random.randint(1, 10),  # Latency sangat rendah
                "session_metrics": {
                    "bytes_sent": random.randint(1000000, 2000000),  # Traffic tinggi
                    "bytes_received": random.randint(2000000, 4000000),
                    "packets_lost": 0,  # Tidak ada packet loss
                    "average_speed": random.randint(50000, 100000),  # Speed sangat tinggi
                    "device_type": "DESKTOP",  # Identifikasi sebagai Desktop App
                    "app_version": "4.29.0",
                    "client_type": "GRASS_DESKTOP",
                    "multiplier_active": True,
                    "multiplier_value": MULTIPLIER
                }
            }
        }

def generate_hardware_id():
    """Generate hardware ID yang konsisten berdasarkan sistem"""
    import platform
    system_info = platform.uname()
    base_info = f"{system_info.system}-{system_info.machine}-{system_info.processor}"
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, base_info))

def convert_http_to_socks5(http_proxy):
    """Mengkonversi format HTTP proxy ke format SOCKS5"""
    try:
        # Format: http://username:password@host:port
        proxy_parts = http_proxy.replace('http://', '').split('@')
        auth = proxy_parts[0]
        host_port = proxy_parts[1]
        
        username, password = auth.split(':')
        host, port = host_port.split(':')
        
        # Format SOCKS5: socks5://username:password@host:port
        return f"socks5://{username}:{password}@{host}:{port}"
    except Exception as e:
        logger.error(f"Error converting proxy format: {e}")
        return None

def get_proxy_info(proxy_url):
    """Mendapatkan informasi detail dari proxy"""
    try:
        # Ambil informasi lokasi berdasarkan IP proxy
        host = proxy_url.split('@')[1].split(':')[0]
        
        # Database kota untuk berbagai negara
        cities = {
            "AU": ["Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide", "Gold Coast", "Canberra"],
            "US": ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Miami", "Seattle"],
            "UK": ["London", "Manchester", "Birmingham", "Leeds", "Liverpool", "Glasgow", "Edinburgh"],
            "CA": ["Toronto", "Vancouver", "Montreal", "Calgary", "Ottawa", "Edmonton"],
            "NZ": ["Auckland", "Wellington", "Christchurch", "Hamilton", "Dunedin"],
            "SG": ["Singapore Central", "Woodlands", "Tampines", "Jurong", "Punggol"],
            "JP": ["Tokyo", "Osaka", "Yokohama", "Nagoya", "Sapporo", "Fukuoka"],
            "KR": ["Seoul", "Busan", "Incheon", "Daegu", "Daejeon", "Gwangju"],
            "DE": ["Berlin", "Hamburg", "Munich", "Cologne", "Frankfurt", "Stuttgart"],
            "FR": ["Paris", "Marseille", "Lyon", "Toulouse", "Nice", "Nantes"],
            "IT": ["Rome", "Milan", "Naples", "Turin", "Florence", "Venice"],
            "ES": ["Madrid", "Barcelona", "Valencia", "Seville", "Bilbao", "Malaga"],
            "NL": ["Amsterdam", "Rotterdam", "The Hague", "Utrecht", "Eindhoven"],
            "SE": ["Stockholm", "Gothenburg", "Malmo", "Uppsala", "Vasteras"],
            "NO": ["Oslo", "Bergen", "Trondheim", "Stavanger", "Drammen"],
            "FI": ["Helsinki", "Espoo", "Tampere", "Vantaa", "Oulu"],
            "DK": ["Copenhagen", "Aarhus", "Odense", "Aalborg", "Frederiksberg"],
            "BR": ["Sao Paulo", "Rio de Janeiro", "Brasilia", "Salvador", "Fortaleza"],
            "AR": ["Buenos Aires", "Cordoba", "Rosario", "Mendoza", "La Plata"],
            "MX": ["Mexico City", "Guadalajara", "Monterrey", "Puebla", "Tijuana"],
            "IN": ["Mumbai", "Delhi", "Bangalore", "Chennai", "Kolkata"],
            "ID": ["Jakarta", "Surabaya", "Bandung", "Medan", "Semarang"],
            "MY": ["Kuala Lumpur", "Johor Bahru", "Penang", "Malacca", "Ipoh"],
            "TH": ["Bangkok", "Nonthaburi", "Nakhon Ratchasima", "Chiang Mai", "Phuket"],
            "VN": ["Ho Chi Minh City", "Hanoi", "Da Nang", "Can Tho", "Bien Hoa"],
            "PH": ["Manila", "Quezon City", "Davao", "Cebu", "Makati"]
        }
        
        # ISP untuk berbagai region
        isps = {
            "AU": ["Telstra", "Optus", "TPG", "iiNet", "Aussie Broadband"],
            "US": ["Comcast", "Verizon", "AT&T", "Spectrum", "Cox"],
            "UK": ["BT", "Virgin Media", "Sky Broadband", "TalkTalk", "Vodafone"],
            "AS": ["NTT", "KDDI", "SoftBank", "Singtel", "Telekom Malaysia"],
            "EU": ["Deutsche Telekom", "Orange", "Telefonica", "Vodafone", "TIM"],
            "OTHER": ["Global ISP", "Network Provider", "Internet Service", "Broadband Plus", "Net Connect"]
        }
        
        # Deteksi region berdasarkan host/IP
        # Ini bisa dikembangkan lebih lanjut dengan database GeoIP yang lebih akurat
        country = "AU"  # Default ke AU, bisa disesuaikan dengan deteksi IP yang lebih akurat
        
        # Pilih ISP berdasarkan region
        region = "AU" if country in ["AU", "NZ"] else \
                "US" if country in ["US", "CA"] else \
                "UK" if country in ["UK", "IE"] else \
                "AS" if country in ["JP", "KR", "SG", "MY", "ID", "TH", "VN", "PH"] else \
                "EU" if country in ["DE", "FR", "IT", "ES", "NL", "SE", "NO", "FI", "DK"] else \
                "OTHER"
        
        return {
            "country": country,
            "city": random.choice(cities.get(country, cities["AU"])),
            "isp": random.choice(isps.get(region, isps["OTHER"])),
            "connection_type": random.choice(["fiber", "cable", "dsl", "ethernet"]),
            "network_speed": random.randint(50, 500),  # Mbps
            "network_type": random.choice(["residential", "datacenter", "mobile"]),
            "asn": f"AS{random.randint(1000, 9999)}",
            "connection_stability": random.uniform(0.95, 0.99),
            "ipv6_supported": random.choice([True, False]),
            "dns_servers": ["8.8.8.8", "8.8.4.4"] if random.random() > 0.5 else ["1.1.1.1", "1.0.0.1"]
        }
    except Exception as e:
        logger.error(f"Error getting proxy info: {e}")
        return None

async def connect_to_wss_instance(proxy_instance: ProxyInstance, user_id: str):
    """Fungsi koneksi untuk satu instance proxy"""
    while True:
        try:
            proxy_info = get_proxy_info(proxy_instance.proxy_url)
            if not proxy_info:
                logger.error(f"Failed to get proxy info for {proxy_instance.proxy_url}")
                return

            custom_headers = {
                "User-Agent": f"WyndVPN/{random.choice(['4.28.1', '4.28.2', '4.28.3'])} (Windows NT 10.0; Win64; x64)",
                "X-Client-Type": "desktop",
                "X-App-Version": "4.28.1",
                "X-Platform": "windows",
                "X-Device-Id": proxy_instance.device_id,
                "X-Installation-Id": proxy_instance.installation_id,
                "X-Instance-Id": str(proxy_instance.instance_id),
                "X-Connection-Type": proxy_info["connection_type"],
                "X-Network-Speed": str(proxy_info["network_speed"]),
                "X-ISP": proxy_info["isp"]
            }

            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            urilist = ["wss://proxy2.wynd.network:4444/","wss://proxy2.wynd.network:4650/"]
            uri = random.choice(urilist)
            server_hostname = "proxy2.wynd.network"
            
            # Konversi format proxy
            socks5_url = convert_http_to_socks5(proxy_instance.proxy_url)
            if not socks5_url:
                raise ValueError(f"Invalid proxy format: {proxy_instance.proxy_url}")
                
            proxy = Proxy.from_url(socks5_url)
            
            async with proxy_connect(
                uri,
                proxy=proxy,
                ssl=ssl_context,
                server_hostname=server_hostname,
                extra_headers=custom_headers,
                timeout=30  # Tambahkan timeout
            ) as websocket:
                
                # Definisikan ping task di luar untuk bisa diakses saat error
                ping_task = None
                
                async def send_ping():
                    try:
                        while True:
                            send_message = json.dumps({
                                "id": str(uuid.uuid4()),
                                "version": "1.0.0",
                                "action": "PING",
                                "data": {}
                            })
                            await websocket.send(send_message)
                            logger.debug(f"Ping sent via proxy {proxy_instance.proxy_url}")
                            await asyncio.sleep(5)
                    except asyncio.CancelledError:
                        logger.debug(f"Ping task cancelled for proxy {proxy_instance.proxy_url}")
                        raise
                    except Exception as e:
                        logger.error(f"Error in ping task for proxy {proxy_instance.proxy_url}: {e}")
                        raise

                await asyncio.sleep(1)
                ping_task = asyncio.create_task(send_ping())

                try:
                    while True:
                        response = await websocket.recv()
                        message = json.loads(response)
                        logger.info(f"[Proxy: {proxy_instance.proxy_url}] Received: {message}")
                        
                        if message.get("action") == "AUTH":
                            auth_response = {
                                "id": message["id"],
                                "origin_action": "AUTH",
                                "result": {
                                    "browser_id": proxy_instance.device_id,
                                    "user_id": user_id,
                                    "user_agent": custom_headers['User-Agent'],
                                    "timestamp": int(time.time()),
                                    "device_type": "desktop",
                                    "version": "4.28.1",
                                    "platform": "windows",
                                    "app_name": "WyndVPN",
                                    "app_version": "4.28.1",
                                    "os": "Windows",
                                    "os_version": "10",
                                    "architecture": "x64",
                                    "screen_resolution": "1920x1080",
                                    "language": "en-US",
                                    "timezone": "UTC+7",
                                    "is_mobile": False,
                                    "is_browser": False,
                                    "is_desktop_app": True,
                                    "cpu_cores": 8,
                                    "memory": 16384,
                                    "connection_type": "ethernet",
                                    "network_type": "residential",
                                    "client_type": "desktop_app",
                                    "installation_id": proxy_instance.installation_id,
                                    "hardware_id": proxy_instance.hardware_id,
                                    "build_number": "20231120",
                                    "client_capabilities": ["proxy", "vpn", "bandwidth"],
                                    "proxy_type": "residential",
                                    "proxy_country": proxy_info["country"],
                                    "proxy_city": proxy_info["city"],
                                    "proxy_isp": proxy_info["isp"],
                                    "connection_quality": "high",
                                    "bandwidth_limit": random.randint(800000, 1200000),
                                    "session_id": str(uuid.uuid4()),
                                    "network_characteristics": {
                                        "connection_type": proxy_info["connection_type"],
                                        "network_speed": proxy_info["network_speed"],
                                        "latency": random.randint(30, 80),
                                        "packet_loss": random.uniform(0, 0.5),
                                        "jitter": random.uniform(1, 5)
                                    }
                                }
                            }
                            await websocket.send(json.dumps(auth_response))
                            logger.info(f"[Proxy: {proxy_instance.proxy_url}] Desktop App Auth response sent")

                        elif message.get("action") == "PONG":
                            pong_response = {
                                "id": message["id"],
                                "origin_action": "PONG"
                            }
                            await websocket.send(json.dumps(pong_response))
                            logger.debug(f"[Proxy: {proxy_instance.proxy_url}] Pong response sent")
                            
                        elif message.get("action") == "TASK":
                            task_data = message.get("data", {})
                            
                            # Optimasi response untuk point maksimal
                            task_response = await proxy_instance.optimize_task_response(message)
                            await websocket.send(json.dumps(task_response))
                            
                            # Update statistik dengan multiplier 2.00x
                            proxy_instance.tasks_completed += 1
                            base_points = random.uniform(2.0, 4.0)  # Base point lebih tinggi
                            multiplied_points = base_points * MULTIPLIER
                            proxy_instance.earnings += multiplied_points
                            
                            logger.info(f"[Desktop 2.00x][Proxy: {proxy_instance.proxy_url}] "
                                      f"Task #{proxy_instance.tasks_completed} completed | "
                                      f"Base Points: {base_points:.2f} | "
                                      f"With Multiplier: {multiplied_points:.2f}")
                            
                            # Minimal delay antara tasks
                            await asyncio.sleep(random.uniform(0.5, 1.5))
                        
                        elif message.get("action") == "BALANCE":
                            balance_response = {
                                "id": message["id"],
                                "origin_action": "BALANCE",
                                "result": {
                                    "status": "success",
                                    "timestamp": int(time.time()),
                                    "balance": 0,
                                    "currency": "USD"
                                }
                            }
                            await websocket.send(json.dumps(balance_response))
                            logger.info(f"[Proxy: {proxy_instance.proxy_url}] Balance request handled")

                except Exception as ws_error:
                    logger.error(f"WebSocket error for proxy {proxy_instance.proxy_url}: {ws_error}")
                    if ping_task:
                        ping_task.cancel()
                    raise

            # Tambahkan rotasi
            current_time = time.time()
            if current_time - proxy_instance.last_rotation >= ROTATION_INTERVAL:
                logger.info(f"Rotating instance {proxy_instance.instance_id} for proxy {proxy_instance.proxy_url}")
                proxy_instance.last_rotation = current_time
                proxy_instance.installation_id = str(uuid.uuid4())  # Generate ID baru
                await asyncio.sleep(random.uniform(1, 5))
                continue

        except Exception as e:
            proxy_instance.error_count += 1
            logger.error(f"Error in instance {proxy_instance.instance_id} for proxy {proxy_instance.proxy_url}: {e}")
            await asyncio.sleep(random.uniform(5, 15))

async def manage_proxy_instances(proxy_url: str, user_id: str):
    """Mengelola multiple instance dengan optimasi earning"""
    try:
        instances = [ProxyInstance(proxy_url, i) for i in range(INSTANCES_PER_PROXY)]
        tasks = []
        
        # Monitor earnings
        async def monitor_earnings():
            while True:
                total_earnings = sum(instance.earnings for instance in instances)
                total_tasks = sum(instance.tasks_completed for instance in instances)
                logger.info(f"Statistik Earning untuk Proxy {proxy_url}:")
                logger.info(f"Total Tasks Completed: {total_tasks}")
                logger.info(f"Total Estimated Earnings: {total_earnings:.2f} GrassCoins")
                logger.info(f"Average Earning per Task: {(total_earnings/total_tasks if total_tasks > 0 else 0):.3f}")
                await asyncio.sleep(60)  # Update setiap menit
        
        # Tambahkan monitoring task
        tasks.append(asyncio.create_task(monitor_earnings()))
        
        # Jalankan instance dengan delay minimal
        for i, instance in enumerate(instances):
            await asyncio.sleep(1)  # Delay 1 detik antar instance
            tasks.append(connect_to_wss_instance(instance, user_id))
        
        await asyncio.gather(*tasks)
        
    except Exception as e:
        logger.error(f"Error in proxy management: {e}")

async def main():
    try:
        _user_id = input('Please Enter your user ID: ').strip()
        if not _user_id:
            raise ValueError("User ID tidak boleh kosong")
        
        try:
            with open('local_proxies.txt', 'r') as file:
                local_proxies = [proxy.strip() for proxy in file.readlines() if proxy.strip()]
            
            if not local_proxies:
                raise FileNotFoundError("Tidak ada proxy yang ditemukan dalam file")
            
            # Hapus duplikat proxy
            local_proxies = list(set(local_proxies))
            logger.info(f"Jumlah proxy unik: {len(local_proxies)}")
            logger.info(f"Total instance yang akan dijalankan: {len(local_proxies) * INSTANCES_PER_PROXY}")
            
            # Batasi jumlah concurrent tasks
            semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
            
            async def run_with_semaphore(proxy):
                async with semaphore:
                    await manage_proxy_instances(proxy, _user_id)
            
            # Jalankan semua proxy dengan batasan concurrent
            tasks = [run_with_semaphore(proxy) for proxy in local_proxies]
            await asyncio.gather(*tasks)
            
        except FileNotFoundError:
            logger.error("File local_proxies.txt tidak ditemukan atau kosong")
            return
        
    except KeyboardInterrupt:
        logger.info("Program dihentikan oleh user")
    except Exception as e:
        logger.error(f"Error dalam main: {str(e)}")

if __name__ == '__main__':
    # Setup logging
    logger.add("proxy_multi_{time}.log", 
               rotation="100 MB", 
               retention="7 days",
               compression="zip",
               enqueue=True)
    
    # Jalankan program
    asyncio.run(main())
