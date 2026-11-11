import hashlib
import os
import shutil
import string
import sys

IS_WINDOWS = os.name == "nt"

if IS_WINDOWS:
    INSTALL_DIR = os.path.join(os.path.expanduser("~"), "HashTool")
else:
    INSTALL_DIR = os.path.expanduser("~/myapps/hash_tool")

RECORDS = os.path.join(INSTALL_DIR, "records.txt")
ME = os.path.abspath(sys.argv[0] if sys.argv else __file__)


# ==========================================================
#  ЧАСТЬ 1: код проверяльщика (его установщик пишет в автозагрузку)
# ==========================================================

def checker_code():
    """Возвращает текст программы-проверяльщика."""
    return '''import hashlib
import os
import shutil

RECORDS = r"{records}"
QUARANTINE = os.path.join(os.path.dirname(RECORDS), "quarantine")


def sha256_of_file(path):
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()


def move_to_quarantine(path):
    os.makedirs(QUARANTINE, exist_ok=True)
    base = os.path.basename(path)
    dest = os.path.join(QUARANTINE, base)
    n = 1
    while os.path.exists(dest):
        dest = os.path.join(QUARANTINE, str(n) + "_" + base)
        n += 1
    shutil.move(path, dest)
    print("   -> Перемещён в карантин:", dest)


def ask_what_to_do(path):
    while True:
        answer = input(
            "   Что делаем? [1] Удалить  [2] В карантин  [3] Оставить: "
        ).strip()
        if answer == "1":
            os.remove(path)
            print("   -> УДАЛЁН:", path)
            return
        if answer == "2":
            move_to_quarantine(path)
            return
        if answer == "3":
            print("   -> Оставлен на месте.")
            return
        print("   Введи 1, 2 или 3")


def main():
    print("=== Проверка файлов (автозапуск) ===")
    if not os.path.isfile(RECORDS):
        print("Список файлов пуст — запусти hash_tool.py и добавь файлы.")
        return

    changed = []
    checked = 0
    with open(RECORDS, encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    for line in lines:
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            continue
        saved_hash, path = parts
        if not os.path.isfile(path):
            print("?? Не найден:", path)
            continue
        checked += 1
        if sha256_of_file(path).lower() == saved_hash.lower():
            print("OK  ", path)
        else:
            print("!!! ИЗМЕНЁН:", path)
            changed.append(path)

    print()
    print("Проверено:", checked, "| Изменённых:", len(changed))

    for path in changed:
        ask_what_to_do(path)

    if not changed:
        print("Всё в порядке! 👍")


main()
'''.format(records=RECORDS)


# ==========================================================
#  ЧАСТЬ 2: установка проверяльщика в автозагрузку
# ==========================================================

def write_autostart():
    if IS_WINDOWS:
        startup = os.path.join(
            os.environ["APPDATA"],
            r"Microsoft\Windows\Start Menu\Programs\Startup",
        )
        os.makedirs(startup, exist_ok=True)

        checker_py = os.path.join(startup, "hash_tool_checker.py")
        with open(checker_py, "w", encoding="utf-8") as f:
            f.write(checker_code())

        bat = os.path.join(startup, "hash_tool_checker.bat")
        with open(bat, "w", encoding="utf-8") as f:
            f.write('@echo off\r\n'
                    f'python "{checker_py}"\r\n'
                    'pause\r\n')
        print(f"💾 В автозагрузку записано: {bat}")
    else:
        autostart_dir = os.path.expanduser("~/.config/autostart")
        os.makedirs(autostart_dir, exist_ok=True)

        checker_sh = os.path.join(autostart_dir, "hash_tool_checker.py")
        with open(checker_sh, "w", encoding="utf-8") as f:
            f.write("#!/usr/bin/env python3\n" + checker_code())
        os.chmod(checker_sh, 0o755)

        desktop = os.path.join(autostart_dir, "hash-tool.desktop")
        with open(desktop, "w", encoding="utf-8") as f:
            f.write("[Desktop Entry]\n"
                    "Type=Application\n"
                    "Name=Hash Checker\n"
                    f"Exec=xterm -e python3 {checker_sh}\n"
                    "Terminal=false\n")
        print(f"💾 В автозагрузку записано: {desktop}")


# ==========================================================
#  ЧАСТЬ 3: выбор диска и файла
# ==========================================================

def list_drives():
    drives = []
    if IS_WINDOWS:
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                drives.append((f"{letter}:", drive))
    else:
        for letter in string.ascii_lowercase:
            mount = f"/mnt/{letter}"
            if os.path.exists(mount):
                drives.append((f"{letter.upper()}:", mount))
        if os.path.exists("/"):
            drives.append(("Система WSL", "/"))
    return drives


def normalize_path(raw, mount):
    path = raw.strip().strip("'\"")
    if IS_WINDOWS:
        path = path.replace("/", "\\")
        if len(path) >= 2 and path[0].isalpha() and path[1] == ":":
            path = path[0].upper() + path[1:]
    else:
        path = path.replace("\\", "/")
        if len(path) >= 2 and path[0].isalpha() and path[1] == ":":
            letter = path[0].upper()
            disk_map = dict(list_drives())
            if f"{letter}:" in disk_map:
                path = disk_map[f"{letter}:"] + path[2:]
            else:
                return None
    if not (path.startswith("/") or (len(path) >= 2 and path[1] == ":")):
        sep = "\\" if IS_WINDOWS else "/"
        path = mount.rstrip("/\\") + sep + path
    return path


def sha256_of_file(path):
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()


# ==========================================================
#  ЧАСТЬ 4: реестр файлов
# ==========================================================

def add_to_records(path, digest):
    os.makedirs(INSTALL_DIR, exist_ok=True)
    lines = []
    if os.path.isfile(RECORDS):
        with open(RECORDS, encoding="utf-8") as f:
            lines = f.read().splitlines()

    # Убираем старую запись про этот же файл, если была
    new_lines = []
    for l in lines:
        parts = l.split(maxsplit=1)
        if len(parts) == 2 and parts[1].strip().lower() == path.lower():
            continue
        new_lines.append(l)
    new_lines.append(f"{digest}  {path}")

    with open(RECORDS, "w", encoding="utf-8") as f:
        f.write("\n".join(new_lines) + "\n")
    print(f"📋 Файл добавлен в реестр: {RECORDS}")


# ==========================================================
#  ЧАСТЬ 5: главная программа (ручной запуск)
# ==========================================================

def choose_disk():
    disks = list_drives()
    print("\n💻 Доступные диски:")
    for label, _ in disks:
        print(f"  {label}")
    while True:
        raw = input("Выбери диск (например C): ").strip().strip("'\"").upper()
        if raw and raw[0].isalpha():
            for label, mount in disks:
                if label.startswith(raw[0]):
                    return label, mount
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(disks):
                return disks[idx]
        print("❌ Такого диска нет, попробуй ещё раз")


def choose_file(mount):
    while True:
        raw = input("Введи путь к файлу (можно с C:\\ или C:/ в начале): ")
        path = normalize_path(raw, mount)
        if path is None:
            print("❌ Не знаю такой диск")
            continue
        if os.path.isfile(path):
            return path
        print(f"❌ Файл не найден: {path}")


def main():
    print("=== 🔍 Hash Tool ===")

    label, mount = choose_disk()
    path = choose_file(mount)

    print("\n⏳ Считаю SHA-256...")
    digest = sha256_of_file(path)
    print(f"🔑 SHA-256: {digest}")

    # Создаём/обновляем запись .sha256 рядом с файлом
    record = path + ".sha256"
    with open(record, "w") as f:
        f.write(f"{digest}  {os.path.basename(path)}\n")
    print(f"💾 Запись создана: {record}")

    # Добавляем в реестр для автопроверки
    add_to_records(path, digest)

    # Записываем проверяльщик в автозагрузку
    try:
        write_autostart()
    except Exception as e:
        print(f"⚠️ Автозагрузка не записалась: {e}")

    print("\nГотово! 👋")


if __name__ == "__main__":
    main()

