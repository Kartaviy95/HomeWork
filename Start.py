import os
import subprocess
from tqdm import tqdm
import _winapi
import datetime
from shutil import rmtree, move
from colorama import Fore, Style
import logging
import shutil
import ctypes
import win32file

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
    Определяет измененные папки в репозитории за последние 'days' дней, исключая папки с именем 'cTab'.
    """
    git_after = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    git_params = ["git", "log", "--after", git_after, "--name-only", "--no-merges"]
    try:
        result = subprocess.run(git_params, cwd=repo_path, stdout=subprocess.PIPE, text=True, check=True)
        changed_files = result.stdout.splitlines()

        # Извлекаем уникальные измененные папки с их родительскими категориями
        changed_folders = set()  # Используем set для исключения дублирующихся папок
        for file_path in changed_files:
            # Добавляем только те папки, которые не являются 'cTab'
            if file_path.startswith("addons/"):
                category = "addons"
                folder = file_path.split("/")[1]
                if folder.lower() == "cTab":  # Исключаем папку 'cTab'
                    continue
                changed_folders.add((folder, category))
            elif file_path.startswith("addons core/"):
                category = "addons core"
                folder = file_path.split("/")[1]
                if folder.lower() == "cTab":  # Исключаем папку 'cTab'
                    continue
                changed_folders.add((folder, category))
            elif file_path.startswith("addons islands/"):
                category = "addons islands"
                folder = file_path.split("/")[1]
                changed_folders.add((folder, category))
            elif file_path.startswith("server/"):
                category = "server"
                folder = file_path.split("/")[1]
                changed_folders.add((folder, category))

        log_and_print(f"Измененные папки за последние {days} дней (исключая cTab): {list(changed_folders)}")
        return list(changed_folders)  # Преобразуем set в list для дальнейшей обработки
    except subprocess.CalledProcessError as e:
        log_and_print(f"Ошибка при выполнении команды git: {e}", level="error")
        return []



def clean_symlinks(custom_addons_folder, protected_folders):
    """
    Очистка всех папок и Junction ссылок в custom_addons_folder,
    за исключением защищенных папок.
    """
    log_and_print(f"Очистка папок и Junction ссылок в {custom_addons_folder}...")

    # Проходим по всем папкам в custom_addons_folder
    for folder in os.listdir(custom_addons_folder):
        folder_path = os.path.join(custom_addons_folder, folder)

        # Пропускаем защищенные папки
        if folder in protected_folders:
            log_and_print(f"Пропуск защищенной папки: {folder_path}")
            continue

        try:
            log_and_print(f"Удаление папки или Junction: {folder_path}")

            # Если это символическая ссылка, удаляем её с помощью os.unlink
            if os.path.islink(folder_path):
                os.unlink(folder_path)  # Удаляем символическую ссылку
            # Если это директория, удаляем её с помощью rmtree
            elif os.path.isdir(folder_path):
                rmtree(folder_path)  # Удаляем папку
            # Если это файл, удаляем его
            elif os.path.isfile(folder_path):
                os.remove(folder_path)  # Удаляем файл
            else:
                log_and_print(f"{folder_path} не является ссылкой, папкой или файлом. Пропуск.")
        except Exception as e:
            log_and_print(f"Ошибка при удалении {folder_path}: {e}", level="error")

def create_junction_alternative(src_dir, dst_dir):
    try:
        ctypes.windll.kernel32.CreateSymbolicLinkW(dst_dir, src_dir, 1)
        log_and_print(f"Создана ссылка (альтернативный метод): {src_dir} -> {dst_dir}")
    except Exception as e:
        log_and_print(f"Ошибка создания Junction (альтернативный метод): {e}", level="error")

def create_junction(src_dir, dst_dir):
    """
    Создаёт Junction link для папки с использованием _winapi, с исключением папки cTab.
    """
    src_dir = os.path.normpath(os.path.realpath(src_dir))
    dst_dir = os.path.normpath(os.path.realpath(dst_dir))

    # Исключение для папки cTab
    if os.path.basename(src_dir).lower() == "ctab":
        log_and_print(f"Пропуск создания ссылки для защищенной папки: {src_dir}")
        return

    if not os.path.exists(src_dir):
        log_and_print(f"Ошибка: Исходная папка {src_dir} не существует.", level="error")
        return

    if os.path.exists(dst_dir):
        if not os.path.isdir(dst_dir):
            log_and_print(f"Ошибка: Целевая папка {dst_dir} не может быть создана. Уже существует файл.", level="error")
            return
        else:
            log_and_print(f"Junction link уже существует: {dst_dir}")
            return

    try:
        os.makedirs(os.path.dirname(dst_dir), exist_ok=True)
        _winapi.CreateJunction(src_dir, dst_dir)
        log_and_print(f"Создан Junction link: {src_dir} -> {dst_dir}")
    except FileNotFoundError as e:
        log_and_print(f"Ошибка при создании Junction: {e}", level="error")



def create_symlinks(changed_folders, do_copy, custom_addons_folder, repo_path):
    """Создание символических ссылок для измененных папок в указанной папке custom_addons_folder."""
    if not do_copy:
        log_and_print("Пропущено создание символических ссылок из-за флага -nc")
        return

    # Защищенные папки, которые не нужно удалять
    protected_folders = {"mkk_sys", "cTab", "mkk_grad_trenches_main"}  # Используем множество для быстрого поиска

    # Папка назначения, где будут создаваться символические ссылки
    release_path = custom_addons_folder  # Используем уже указанный путь
    os.makedirs(release_path, exist_ok=True)  # Убедимся, что целевая папка существует

    log_and_print("\nСписок измененных папок:")

    # Группируем изменения по папкам, чтобы создать символическую ссылку только для папки
    processed_folders = set()  # Используем set для предотвращения повторного создания ссылок для одной папки

    for folder, category in changed_folders:
        # Пропускаем папку cTab или другие защищенные папки
        if folder.lower() in protected_folders:
            log_and_print(f"Пропуск создания символической ссылки для защищенной папки: {folder}")
            continue

        # Пропускаем папки, для которых уже была создана ссылка
        if folder in processed_folders:
            continue

        # Добавляем папку в список обработанных
        processed_folders.add(folder)

        # Определяем полный путь к папке в репозитории
        folder_path = os.path.join(repo_path, category, folder)
        symlink_path = os.path.join(custom_addons_folder, folder)

        log_and_print(f"Путь к папке в репозитории: {folder_path}")
        log_and_print(f"Путь для символической ссылки: {symlink_path}")

        # Создание Junction link для папки
        create_junction(folder_path, symlink_path)



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


def obfuscate_files_with_shortcut(makepbo_bat_path, obfuscation_folders, addons_folder, target_folder):
    """
    Обфускация файлов через MakePbo (через .bat файл), скрывая вывод и отображая шкалу выполнения для каждого файла.
    """
    # Используем tqdm для отслеживания прогресса по обфускации
    for folder in obfuscation_folders:
        folder_path = os.path.join(addons_folder, folder)
        if not os.path.isdir(folder_path):
            log_and_print(f"Ошибка: Папка {folder_path} не найдена.", level="warning")
            continue

        log_and_print(f"Запуск обфускации для папки: {folder_path}")

        try:
            # Применяем tqdm для отслеживания прогресса
            with tqdm(total=1, desc=f"Обфускация {folder}", ncols=100, bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt}") as pbar:
                # Вызываем .bat файл с передачей пути к папке
                subprocess.run(["cmd", "/c", makepbo_bat_path, folder_path], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
    """Перемещает .pbo файлы в соответствующие папки для модов, островов, серверов и ядра, затем удаляет оставшиеся .pbo файлы в target_folder."""
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

            try:
                # Проверяем, существует ли исходный файл перед перемещением
                if os.path.exists(source_pbo_path):
                    shutil.move(source_pbo_path, target_pbo_path)
                    log_and_print(f"Перемещен файл {pbo_file_name} из {category} в {target_path}")
                else:
                    log_and_print(f"Файл {pbo_file_name} не найден в {target_folder}", level="warning")
            except Exception as e:
                log_and_print(f"Ошибка при перемещении {pbo_file_name}: {e}", level="error")

    # Удаление оставшихся .pbo файлов в target_folder
    log_and_print(f"\nУдаление оставшихся .pbo файлов в {target_folder}...")
    for file_name in os.listdir(target_folder):
        if file_name.endswith(".pbo"):
            file_path = os.path.join(target_folder, file_name)
            try:
                # Проверяем, существует ли файл перед удалением
                if os.path.exists(file_path):
                    os.remove(file_path)
                    log_and_print(f"Файл {file_name} удалён из {target_folder}")
            except Exception as e:
                log_and_print(f"Ошибка при удалении {file_name} из {target_folder}: {e}", level="error")

def main():
    # Путь до репозитория
    repo_path = r"F:\Arma3\github\MKK-MODES"
    # Основная папка, где будет собираться все символические ссылки
    custom_addons_folder = r"F:\Arma3\Realese\addons"
    # Путь до основны hemtt
    custom_hemtt_path = r"F:\Arma3\Realese"
    # Путь до файла обфускации (поменять так же путь внутри .bat файла)
    custom_makepbo_bat_path = r"F:\Arma3\Realese\tools\obf.bat"
    # Путь до конечной папки, где будут создавать выходные .pbo файлы и папка с полным обновлением
    target_folder = r"F:\Arma3\Realese\.hemttout\release\addons"
    days = 31  # Задайте количество дней для сканирования изменений

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
        obfuscate_files_with_shortcut(custom_makepbo_bat_path, obfuscation_folders, custom_addons_folder, target_folder)

    move_pbos_to_target(target_folder, changed_folders)  # Передаем измененные папки

    log_and_print(Fore.GREEN + "РЕЛИЗ ПОДГОТОВЛЕН" + Style.RESET_ALL)


if __name__ == "__main__":
    main()
