import os
import subprocess
from tqdm import tqdm
import datetime
from shutil import rmtree, move
from colorama import Fore, Style
import logging
import time
import shutil

# Настройка логирования
log_file = "script_logs.log"
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

def log_and_print(message, level="info"):
    """Логирует сообщение и выводит его в консоль."""
    print(message)
    if level == "info":
        logging.info(message)
    elif level == "warning":
        logging.warning(message)
    elif level == "error":
        logging.error(message)


def find_changed_folders(repo_path, days):
    """
    Определяет измененные папки в репозитории за последние 'days' дней, включая папки addons_core, addons_islands и server.
    Возвращает список кортежей вида (папка, категория), где категория это родительская папка.
    """
    git_after = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    git_params = ["git", "log", "--after", git_after, "--name-only", "--no-merges"]
    try:
        result = subprocess.run(git_params, cwd=repo_path, stdout=subprocess.PIPE, text=True, check=True)
        changed_files = result.stdout.splitlines()

        # Извлекаем уникальные измененные папки с их родительскими категориями
        changed_folders = []
        for file_path in changed_files:
            if file_path.startswith("addons/"):
                category = "addons"
                folder = file_path.split("/")[1]
                changed_folders.append((folder, category))
            elif file_path.startswith("addons core/"):
                category = "addons core"
                folder = file_path.split("/")[1]
                changed_folders.append((folder, category))
            elif file_path.startswith("addons islands/"):
                category = "addons islands"
                folder = file_path.split("/")[1]
                changed_folders.append((folder, category))
            elif file_path.startswith("server/"):
                category = "server"
                folder = file_path.split("/")[1]
                changed_folders.append((folder, category))

        log_and_print(f"Измененные папки за последние {days} дней: {changed_folders}")
        return changed_folders
    except subprocess.CalledProcessError as e:
        log_and_print(f"Ошибка при выполнении команды git: {e}", level="error")
        return []

def clean_symlinks(custom_addons_folder, protected_folders):
    """
    Очистка устаревших папок и Junction ссылок в custom_addons_folder,
    за исключением защищенных папок.
    """
    log_and_print(f"Очистка папок и Junction ссылок в {custom_addons_folder}...")

    for folder in os.listdir(custom_addons_folder):
        folder_path = os.path.join(custom_addons_folder, folder)

        # Пропускаем защищенные папки
        if folder in protected_folders:
            log_and_print(f"Пропуск защищенной папки: {folder_path}")
            continue

        # Удаляем папки или Junction
        try:
            log_and_print(f"Удаление папки или Junction: {folder_path}")
            if os.path.islink(folder_path) or (os.path.isdir(folder_path) and not os.path.ismount(folder_path)):
                os.unlink(folder_path)  # Удаляем Junction или символическую ссылку
            elif os.path.isdir(folder_path):
                rmtree(folder_path)  # Удаляем папку
            else:
                log_and_print(f"{folder_path} не является ссылкой или папкой. Пропуск.")
        except Exception as e:
            log_and_print(f"Ошибка при удалении {folder_path}: {e}", level="error")


def create_symlinks(changed_folders, do_copy, custom_addons_folder, repo_path):
    """Создание символических ссылок для измененных папок в указанной папке custom_addons_folder."""
    if not do_copy:
        log_and_print("Пропущено создание символических ссылок из-за флага -nc")
        return

    # Защищенные папки, которые не нужно удалять
    protected_folders = ["mkk_sys"]
    clean_symlinks(custom_addons_folder, protected_folders)

    # Папка назначения, где будут создаваться символические ссылки
    release_path = custom_addons_folder  # Используем уже указанный путь
    os.makedirs(release_path, exist_ok=True)  # Убедимся, что целевая папка существует

    log_and_print("\nСписок измененных папок:")
    for folder, category in changed_folders:
        # Определяем полный путь к папке в репозитории
        folder_path = os.path.join(repo_path, category, folder)  # Теперь добавляется и категория
        symlink_path = os.path.join(release_path, folder)  # Путь символической ссылки

        log_and_print(f"Путь к папке в репозитории: {folder_path}")
        log_and_print(f"Путь для символической ссылки: {symlink_path}")

        if not os.path.isdir(folder_path):
            log_and_print(f"Ошибка: Папка {folder_path} не существует или не является директорией.", level="error")
            continue

        if os.path.exists(symlink_path):
            log_and_print(f"Удаление существующей ссылки или папки: {symlink_path}")
            try:
                if os.path.islink(symlink_path):
                    os.unlink(symlink_path)
                elif os.path.isdir(symlink_path):
                    rmtree(symlink_path)
            except Exception as e:
                pass

        try:
            log_and_print(f"Создание символической ссылки: {symlink_path} -> {folder_path}")
            os.system(f'mklink /J "{symlink_path}" "{folder_path}"')
            log_and_print(f"Символическая ссылка создана: {symlink_path} -> {folder_path}")
        except Exception as e:
            log_and_print(f"Ошибка при создании символической ссылки для {folder}: {e}", level="error")


def run_hemtt(custom_hemtt_path):
    r"""Запуск команды `.\tools\hemtt.exe release` из кастомного места."""
    try:
        os.chdir(custom_hemtt_path)
        hemtt_path = os.path.join(custom_hemtt_path, "tools", "hemtt.exe")
        subprocess.run([hemtt_path, "release"], check=True)
        log_and_print("Команда 'hemtt release' успешно выполнена.")
    except subprocess.CalledProcessError as e:
        log_and_print(f"Ошибка при выполнении hemtt.exe: {e}", level="error")
    except FileNotFoundError as e:
        log_and_print(f"Файл hemtt.exe не найден: {e}", level="error")


def find_obfuscation_folders(addons_folder):
    """Определяет папки для обфускации на основе config.cpp."""
    obfuscation_folders = []
    for folder in os.listdir(addons_folder):
        folder_path = os.path.join(addons_folder, folder)
        if not os.path.isdir(folder_path):
            continue

        config_path = os.path.join(folder_path, "config.cpp")
        if os.path.isfile(config_path):
            try:
                with open(config_path, "r", encoding="utf8") as f:
                    if "mkk_shield=1" in f.read():
                        obfuscation_folders.append(folder)
                        log_and_print(f"Добавлена папка для обфускации: {folder}")
            except Exception as e:
                log_and_print(f"Ошибка при чтении файла {config_path}: {e}", level="error")
    return obfuscation_folders


def obfuscate_files_with_shortcut(makepbo_shortcut, obfuscation_folders, addons_folder, target_folder):
    """Обфускация файлов через MakePbo, скрывая вывод и отображая шкалу выполнения для каждого файла."""

    # Используем tqdm для отображения прогресса по обфускации
    for folder in obfuscation_folders:
        folder_path = os.path.join(addons_folder, folder)
        if not os.path.isdir(folder_path):
            log_and_print(f"Ошибка: Папка {folder_path} не найдена.", level="warning")
            continue

        log_and_print(f"Запуск обфускации для папки: {folder_path}")

        try:
            # Применяем tqdm для отслеживания прогресса
            # Можно сделать прогресс для каждого файла, если известно количество файлов.
            # Но для этого примера мы просто показываем прогресс для каждой обфускации папки.

            # Обновляем прогресс на каждом шаге
            with tqdm(total=1, desc=f"Обфускация {folder}", ncols=100, bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt}") as pbar:
                subprocess.run(["cmd", "/c", makepbo_shortcut, folder_path], check=True, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                pbar.update(1)  # Обновляем прогресс

            # Перемещение файла в целевую папку
            pbo_file_name = f"{folder}.pbo"
            source_pbo_path = os.path.join(addons_folder, pbo_file_name)

            if os.path.isfile(source_pbo_path):
                target_pbo_path = os.path.join(target_folder, pbo_file_name)
                move(source_pbo_path, target_pbo_path)
                log_and_print(f".pbo файл {pbo_file_name} перемещен в {target_folder}")
            else:
                log_and_print(f"Ошибка: .pbo файл {pbo_file_name} не найден после обфускации.", level="warning")
        except Exception as e:
            log_and_print(f"Ошибка при обфускации папки {folder_path}: {e}", level="error")


def move_pbos_to_target(target_folder, changed_folders):
    """Перемещает .pbo файлы в соответствующие папки для модов, островов, серверов и ядра."""
    current_date = datetime.datetime.now().strftime("%Y-%m-%d")
    update_base_path = os.path.join(target_folder, f"update_{current_date}")
    os.makedirs(update_base_path, exist_ok=True)

    # Папки для каждого типа .pbo файлов
    move_to_paths = {
        "addons": os.path.join(update_base_path, "@sg_mods", "addons"),
        "addons islands": os.path.join(update_base_path, "@sg_islands", "addons"),
        "addons core": os.path.join(update_base_path, "@sg_core", "addons"),
        "server": os.path.join(update_base_path, "@sg_server", "addons"),
    }

    # Создаем целевые папки, если они не существуют
    for path in move_to_paths.values():
        os.makedirs(path, exist_ok=True)

    # Перемещение файлов в соответствующие папки
    for folder, category in changed_folders:
        pbo_file_name = f"{folder}.pbo"
        source_pbo_path = os.path.join(target_folder, pbo_file_name)

        # Определяем правильную папку назначения
        target_path = move_to_paths.get(category)
        if target_path:
            target_pbo_path = os.path.join(target_path, pbo_file_name)

            # Перемещаем файл
            try:
                shutil.move(source_pbo_path, target_pbo_path)

                # Добавляем задержку, чтобы файловая система успела обработать перемещение
                time.sleep(0.5)  # Задержка в 1 секунду

                # Проверка существования файла в целевой папке
                if os.path.exists(target_pbo_path):
                    log_and_print(f"Перемещен файл {pbo_file_name} из {category} в {target_path}")
                else:
                    log_and_print(f"Ошибка: Файл {pbo_file_name} не найден в целевой папке после перемещения.", level="error")
            except Exception as e:
                # Убрана строка логирования о неудаче
                pass


def main():
    repo_path = "F:\\Arma3\\github\\MKK-MODES"
    custom_addons_folder = "F:\\Arma3\\Realese\\addons"
    custom_hemtt_path = "F:\\Arma3\\Realese"
    custom_makepbo_shortcut = "F:\\Arma3\\Realese\\tools\\MakePbo2.lnk"
    target_folder = "F:\\Arma3\\Realese\\.hemttout\\release\\addons"
    days = 2  # Задайте количество дней для сканирования изменений

    # Найти измененные папки за последние N дней
    changed_folders = find_changed_folders(repo_path, days)
    if not changed_folders:
        log_and_print("Изменений за указанный период не найдено.", level="warning")
        return

    do_copy = True
    log_and_print(f"Создание символических ссылок: {'включено' if do_copy else 'выключено'}")

    create_symlinks(changed_folders, do_copy, custom_addons_folder, repo_path)  # Передаем измененные папки
    run_hemtt(custom_hemtt_path)

    obfuscation_folders = find_obfuscation_folders(custom_addons_folder)
    if obfuscation_folders:
        obfuscate_files_with_shortcut(custom_makepbo_shortcut, obfuscation_folders, custom_addons_folder, target_folder)

    move_pbos_to_target(target_folder, changed_folders)  # Передаем измененные папки

    log_and_print(Fore.GREEN + "РЕЛИЗ ПОДГОТОВЛЕН" + Style.RESET_ALL)


if __name__ == "__main__":
    main()
