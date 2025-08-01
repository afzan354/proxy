import requests
import csv
import shutil
import os
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

def check_proxy_single(ip, port, api_url_template):
    """
    Mengecek satu proxy menggunakan API.
    """
    try:
        # Format URL API untuk satu proxy
        api_url = api_url_template.format(ip=ip, port=port)
        response = requests.get(api_url, timeout=60)
        response.raise_for_status()
        data = response.json()

        # Ambil status proxyip
        status = data[0].get("proxyip", False)
        country_code = data[0].get("countryCode", None)  # Mendapatkan kode negara
        isp = data[0].get("asOrganization", None)  # Mendapatkan nama ISP
        if status:
            print(f"{ip}:{port} is ALIVE")
            return (ip, port, country_code, isp, None)  # Format: (ip, port, cc, isp, None)
        else:
            print(f"{ip}:{port} is DEAD")
            return (None, None, None, None, f"{ip}:{port} is DEAD")  # Format: (None, None, error_message)
    except requests.exceptions.RequestException as e:
        error_message = f"Error checking {ip}:{port}: {e}"
        print(error_message)
        return (None, None, None, None, error_message)
    except ValueError as ve:
        error_message = f"Error parsing JSON for {ip}:{port}: {ve}"
        print(error_message)
        return (None, None, None, None, error_message)


def generate_kv_proxylist_json(proxy_data, output_file='kvProxylist.json'):
    """
    Mengelompokkan proxy hidup berdasarkan country code (CC),
    dan menyimpan dalam format { "CC": [list of proxies] }.
    """
    grouped = {}

    # Kelompokkan berdasarkan cc
    for ip, port, cc, _, _ in proxy_data:
        if cc not in grouped:
            grouped[cc] = []
        grouped[cc].append(f"{ip}:{port}")

    # Simpan ke file JSON
    try:
        with open(output_file, 'w') as f:
            json.dump(grouped, f, indent=2)
        print(f"File JSON berhasil dibuat: {output_file}")
    except Exception as e:
        print(f"Error saat menyimpan file JSON: {e}")


def save_active_proxies_to_csv(proxy_data, output_file='active_proxies.csv'):
    """
    Menyimpan proxy yang aktif ke dalam file CSV dengan format: ip, port, cc, isp
    """
    try:
        with open(output_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["IP", "Port", "Country Code", "ISP"])
            for ip, port, cc, isp, _ in proxy_data:
                writer.writerow([ip, port, cc, isp])  # Tulis IP, Port, CC, ISP ke file
        print(f"File CSV berhasil dibuat: {output_file}")
    except Exception as e:
        print(f"Error saat menyimpan file CSV: {e}")


def main():
    input_file = os.getenv('IP_FILE', 'totalproxylist.txt')  # File input (default)
    output_file = 'totalproxylist.tmp'  # File output sementara
    error_file = 'error.txt'  # File untuk error
    api_url_template = os.getenv('API_URL', 'https://proxyip-check.vercel.app/{ip}:{port}')

    alive_proxies = []  # Menyimpan proxy yang aktif dengan format [ip, port, cc, isp]
    error_logs = []  # Menyimpan pesan error

    try:
        with open(input_file, "r") as f:
            reader = csv.reader(f)
            rows = list(reader)
        print(f"Memproses {len(rows)} baris dari file input.")
    except FileNotFoundError:
        print(f"File {input_file} tidak ditemukan.")
        return

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for row in rows:
            if len(row) >= 2:
                ip, port = row[0].strip(), row[1].strip()
                futures.append(executor.submit(check_proxy_single, ip, port, api_url_template))

        for future in as_completed(futures):
            ip, port, cc, isp, error = future.result()
            if ip and port:
                # Cari baris yang sesuai dari file input
                for row in rows:
                    if row[0].strip() == ip and row[1].strip() == port:
                        alive_proxies.append((ip, port, cc, isp))  # Simpan ip, port, cc, isp
                        break
            if error:
                error_logs.append(error)

    # Tulis proxy yang aktif ke file output sementara
    try:
        with open(output_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerows([(ip, port, cc, isp) for ip, port, cc, isp in alive_proxies])
        print(f"File output {output_file} telah diperbarui.")
    except Exception as e:
        print(f"Error menulis ke {output_file}: {e}")
        return

    # Tulis error ke file error.txt
    if error_logs:
        try:
            with open(error_file, "w") as f:
                for error in error_logs:
                    f.write(error + "\n")
            print(f"Beberapa error telah dicatat di {error_file}.")
        except Exception as e:
            print(f"Error menulis ke {error_file}: {e}")
            return

    # Ganti file input dengan file output
    try:
        shutil.move(output_file, input_file)
        print(f"{input_file} telah diperbarui dengan proxy yang ALIVE.")
    except Exception as e:
        print(f"Error menggantikan {input_file}: {e}")

    # Buat dua file JSON berdasarkan pengelompokan
    generate_kv_proxylist_json(alive_proxies)  # Menyimpan ke kvProxylist.json
    save_active_proxies_to_csv(alive_proxies)  # Menyimpan ke active_proxies.csv


if __name__ == "__main__":
    main()
