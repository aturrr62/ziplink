from flask import Flask, jsonify, request, redirect
import mysql.connector
import os
import random
import string
import time
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Fungsi koneksi ke MySQL Railway
def get_db():
    return mysql.connector.connect(
        host=os.environ.get("MYSQLHOST"),
        port=int(os.environ.get("MYSQLPORT", 3306)),
        user=os.environ.get("MYSQLUSER"),
        password=os.environ.get("MYSQLPASSWORD"),
        database=os.environ.get("MYSQLDATABASE")
    )

# Inisialisasi tabel saat aplikasi pertama jalan (dengan retry)
def init_db(max_retries=10, delay=3):
    for attempt in range(1, max_retries + 1):
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS links (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    kode VARCHAR(10) UNIQUE NOT NULL,
                    url_asli TEXT NOT NULL,
                    kunjungan INT DEFAULT 0,
                    dibuat_pada TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            cur.close()
            conn.close()
            print(f"[DB] Berhasil terhubung dan tabel siap (percobaan ke-{attempt})")
            return
        except Exception as e:
            print(f"[DB] Percobaan ke-{attempt} gagal: {e}")
            if attempt < max_retries:
                print(f"[DB] Mencoba lagi dalam {delay} detik...")
                time.sleep(delay)
            else:
                print("[DB] PERINGATAN: Gagal inisialisasi database setelah semua percobaan.")

# Fungsi buat kode acak 6 karakter
def buat_kode():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=6))


# ENDPOINT 1 — Beranda
@app.route('/')
def beranda():
    return jsonify({
        'nama': 'ZipLink',
        'deskripsi': 'Layanan Pemendek URL Sederhana',
        'versi': '1.0.0',
        'status': 'aktif'
    })


# ENDPOINT 2 — Health Check
@app.route('/health')
def health_check():
    try:
        conn = get_db()
        conn.close()
        return jsonify({'status': 'sehat', 'database': 'terhubung'})
    except Exception as e:
        return jsonify({'status': 'tidak sehat', 'error': str(e)}), 500


# ENDPOINT 3 — Buat URL Pendek
@app.route('/shorten', methods=['POST'])
def shorten():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({'error': 'URL diperlukan dalam body JSON'}), 400

    url_asli = data['url']
    kode = buat_kode()
    base_url = os.environ.get("BASE_URL", "http://localhost:5000")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO links (kode, url_asli) VALUES (%s, %s)", (kode, url_asli))
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({
        'url_asli': url_asli,
        'url_pendek': f"{base_url}/{kode}",
        'kode': kode
    }), 201


# ENDPOINT 4 — Redirect ke URL Asli
@app.route('/<kode>')
def redirect_url(kode):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT url_asli FROM links WHERE kode = %s", (kode,))
    hasil = cur.fetchone()

    if not hasil:
        cur.close()
        conn.close()
        return jsonify({'error': 'URL tidak ditemukan'}), 404

    cur.execute("UPDATE links SET kunjungan = kunjungan + 1 WHERE kode = %s", (kode,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(hasil[0])


# ENDPOINT 5 — Statistik Kunjungan
@app.route('/stats/<kode>')
def statistik(kode):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT kode, url_asli, kunjungan, dibuat_pada FROM links WHERE kode = %s",
        (kode,)
    )
    hasil = cur.fetchone()
    cur.close()
    conn.close()

    if not hasil:
        return jsonify({'error': 'Kode tidak ditemukan'}), 404

    return jsonify({
        'kode': hasil[0],
        'url_asli': hasil[1],
        'total_kunjungan': hasil[2],
        'dibuat_pada': str(hasil[3])
    })


# Inisialisasi tabel saat modul pertama kali di-load (termasuk oleh gunicorn)
init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)