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

user_agent = UserAgent(os='windows', platforms='pc', browsers='chrome')
random_user_agent = user_agent.random

async def connect_to_wss(socks5_proxy, user_id):
    max_retries = 10
    retry_delay = 30
    
    device_id = str(uuid.uuid4())
    logger.info(f"Device ID: {device_id}")
    
    while True:
        for retry in range(max_retries):
            try:
                await asyncio.sleep(random.uniform(5, 10))
                
                custom_headers = {
                    "User-Agent": user_agent.random,
                    "Accept": "*/*",
                    "Connection": "keep-alive"
                }
                
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                urilist = ["wss://proxy2.wynd.network:4444/","wss://proxy2.wynd.network:4650/"]
                uri = random.choice(urilist)
                server_hostname = "proxy2.wynd.network"
                proxy = Proxy.from_url(socks5_proxy)
                async with proxy_connect(uri, proxy=proxy, ssl=ssl_context, server_hostname=server_hostname,
                                         extra_headers=custom_headers) as websocket:
                    async def send_ping():
                        try:
                            while True:
                                send_message = json.dumps(
                                    {"id": str(uuid.uuid4()), "version": "1.0.0", "action": "PING", "data": {}})
                                logger.debug(f"Sending ping: {send_message}")
                                await websocket.send(send_message)
                                await asyncio.sleep(5)
                        except Exception as e:
                            logger.error(f"Error in ping task: {e}")

                    await asyncio.sleep(1)
                    asyncio.create_task(send_ping())

                    while True:
                        response = await websocket.recv()
                        message = json.loads(response)
                        logger.info(message)
                        if message.get("action") == "AUTH":
                            auth_response = {
                                "id": message["id"],
                                "origin_action": "AUTH",
                                "result": {
                                    "browser_id": device_id,
                                    "user_id": user_id,
                                    "user_agent": custom_headers['User-Agent'],
                                    "timestamp": int(time.time()),
                                    "device_type": "desktop",
                                    "version": "4.28.1",
                                }
                            }
                            logger.debug(auth_response)
                            await websocket.send(json.dumps(auth_response))

                        elif message.get("action") == "PONG":
                            pong_response = {"id": message["id"], "origin_action": "PONG"}
                            logger.debug(pong_response)
                            await websocket.send(json.dumps(pong_response))
            except Exception as e:
                logger.error(f"Koneksi error untuk proxy {socks5_proxy}: {e}")
                await asyncio.sleep(retry_delay)
                continue
            
        logger.info(f"Memulai ulang koneksi untuk proxy {socks5_proxy}")
        await asyncio.sleep(60)

async def main():
    try:
        _user_id = input('Please Enter your user ID: ').strip()
        if not _user_id:
            raise ValueError("User ID cannot be empty")
            
        try:
            with open('local_proxies.txt', 'r') as file:
                local_proxies = [proxy.strip() for proxy in file.readlines() if proxy.strip()]
                
            if not local_proxies:
                raise ValueError("No valid proxies found in local_proxies.txt")
                
        except FileNotFoundError:
            logger.error("local_proxies.txt not found!")
            return
            
        tasks = [connect_to_wss(proxy, _user_id) for proxy in local_proxies]
        await asyncio.gather(*tasks, return_exceptions=True)
        
    except Exception as e:
        logger.error(f"Main error: {e}")

if __name__ == '__main__':
    #letsgo
    asyncio.run(main())
