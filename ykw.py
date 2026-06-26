import requests
import os
def download_patch(server_url, save_directory):
    url = f"{server_url.rstrip('/')}/getpatch"
    local_filename = os.path.join(save_directory, "patch.exe")
    
    # Fake a real Google Chrome browser request
    custom_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive"
    }
    
    try:
        print(f"Requesting patch from {url}...")
        
        # Pass the headers into the request
        response = requests.get(url, stream=True, headers=custom_headers)
        
        if response.status_code == 200:
            total_size = int(response.headers.get('content-length', 0))
            bytes_downloaded = 0
            
            print(f"Expected file size: {total_size} bytes. Downloading...")
            
            with open(local_filename, "wb") as f:
                while True:
                    chunk = response.raw.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
                    bytes_downloaded += len(chunk)
            
            print(f"Downloaded total: {bytes_downloaded} bytes.")
            
            if total_size != 0 and bytes_downloaded != total_size:
                print(f"[Error] Size mismatch! Got {bytes_downloaded}/{total_size} bytes.")
                if os.path.exists(local_filename):
                    os.remove(local_filename)
                return None
                
            print(f"[Success] Match verified. Saved to: {local_filename}")
            return local_filename
        else:
            print(f"[Error] Server status: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"[Exception] Failed: {e}")
        return None
URL = "http://192.168.1.184:5000/"
download_patch(URL,"")