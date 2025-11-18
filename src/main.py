#!/usr/bin/env python3
import argparse
import sys
import os
import requests
import json
import re
from urllib.parse import urljoin
from collections import deque

class DependencyFetcher:
    def __init__(self, base_url):
        self.base_url = base_url
        self.session = requests.Session()
    
    def get_package_dependencies(self, package_name, version):
        """Получает прямые зависимости пакета"""
        try:
            if "test" in self.base_url:
                return self._get_test_dependencies(package_name, version)
                
            package_url = f"{self.base_url}{package_name.lower()}/index.json"
            response = self.session.get(package_url)
            response.raise_for_status()
            
            package_data = response.json()
            
            # NuGet API v3 использует вложенную структуру items
            items = package_data.get('items', [])
            pages_to_check = []
            
            for item in items:
                version_items = item.get('items', [])
                
                if version_items:
                    # Ищем нужную версию во вложенных items
                    for version_entry in version_items:
                        catalog_entry = version_entry.get('catalogEntry', {})
                        if catalog_entry.get('version') == version:
                            # Если данные версии уже есть в entry, используем их
                            if 'catalogEntry' in version_entry:
                                cat_entry = version_entry['catalogEntry']
                                if 'dependencyGroups' in cat_entry:
                                    return self._extract_dependencies(version_entry)
                            
                            # Иначе получаем детали версии по ссылке
                            version_url = version_entry.get('@id')
                            if version_url:
                                version_response = self.session.get(version_url)
                                version_response.raise_for_status()
                                version_data = version_response.json()
                                return self._extract_dependencies(version_data)
                else:
                    # Если нет вложенных items, это может быть ссылка на страницу
                    if 'catalogEntry' in item:
                        catalog_entry = item['catalogEntry']
                        if catalog_entry.get('version') == version:
                            return self._extract_dependencies(item)
                    # Сохраняем ссылку на страницу для последующей проверки
                    item_url = item.get('@id')
                    if item_url:
                        pages_to_check.append(item_url)
            
            # Проверяем дополнительные страницы (пагинация)
            for page_url in pages_to_check:
                page_response = self.session.get(page_url)
                page_response.raise_for_status()
                page_data = page_response.json()
                
                page_items = page_data.get('items', [])
                for version_entry in page_items:
                    catalog_entry = version_entry.get('catalogEntry', {})
                    if catalog_entry.get('version') == version:
                        # Если данные версии уже есть в entry, используем их
                        if 'catalogEntry' in version_entry:
                            cat_entry = version_entry['catalogEntry']
                            if 'dependencyGroups' in cat_entry:
                                return self._extract_dependencies(version_entry)
                        
                        # Иначе получаем детали версии по ссылке
                        version_url = version_entry.get('@id')
                        if version_url:
                            version_response = self.session.get(version_url)
                            version_response.raise_for_status()
                            version_data = version_response.json()
                            return self._extract_dependencies(version_data)
            
            raise ValueError(f"Версия {version} не найдена для пакета {package_name}")
            
        except requests.RequestException as e:
            raise Exception(f"Ошибка сети: {e}")
        except json.JSONDecodeError as e:
            raise Exception(f"Ошибка парсинга JSON: {e}")
    
    def _extract_dependencies(self, version_data):
        """Извлекает зависимости из данных версии"""
        dependencies = []
        seen_ids = set()  # Для отслеживания уже добавленных зависимостей
        
        # Проверяем, что version_data - словарь
        if not isinstance(version_data, dict):
            return dependencies
        
        # Ищем зависимости в catalogEntry
        catalog_entry = version_data.get('catalogEntry', {})
        if not catalog_entry and isinstance(version_data, dict):
            catalog_entry = version_data
        
        if not isinstance(catalog_entry, dict):
            return dependencies
        
        dependency_groups = catalog_entry.get('dependencyGroups', [])
        
        for group in dependency_groups:
            if not isinstance(group, dict):
                continue
            deps = group.get('dependencies', [])
            for dep in deps:
                if not isinstance(dep, dict):
                    continue
                dep_id = dep.get('id')
                if not dep_id:
                    continue
                # Добавляем только уникальные зависимости
                if dep_id not in seen_ids:
                    seen_ids.add(dep_id)
                    dependencies.append({
                        'id': dep_id,
                        'version_range': dep.get('range', '')
                    })
        
        return dependencies
    
    def _get_test_dependencies(self, package_name, version):
        try:
            # Читаем файл если source указывает на файл
            if self.base_url.startswith("file://"):
                file_path = self.base_url[7:]  # убираем "file://"
                return self._read_dependencies_from_file(file_path, package_name)
            else:
                # Старая логика для обратной совместимости
                test_graph = {
                    'A': ['B', 'C'],
                    'B': ['D'], 
                    'C': ['E', 'F'],
                    'D': ['G'],
                    'E': ['B'],
                    'F': [],
                    'G': ['H'],
                    'H': []
                }
                return [{'id': dep, 'version_range': '1.0.0'} for dep in test_graph.get(package_name, [])]
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Файл не найден: {e}")
        except Exception as e:
            raise Exception(f"Ошибка чтения тестового файла: {e}")

    def _read_dependencies_from_file(self, file_path, package_name):
        """Читает зависимости из текстового файла"""
        dependencies = []
        
        # Преобразуем относительный путь в абсолютный, если нужно
        if not os.path.isabs(file_path):
            # Если путь относительный, делаем его относительно рабочей директории
            file_path = os.path.abspath(file_path)
        
        # Проверяем существование файла
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Файл не найден: {file_path}")
        
        if not os.path.isfile(file_path):
            raise ValueError(f"Путь не является файлом: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                for line in file:
                    line = line.strip()
                    # Пропускаем пустые строки и комментарии
                    if not line or line.startswith('#'):
                        continue
                        
                    # Парсим строку формата "A -> B, C"
                    if '->' in line:
                        parts = line.split('->')
                        current_package = parts[0].strip()
                        
                        if current_package == package_name:
                            deps_str = parts[1].split('#')[0].strip()  # убираем комментарий
                            if deps_str:
                                deps_list = [dep.strip() for dep in deps_str.split(',')]
                                dependencies.extend([{'id': dep, 'version_range': '1.0.0'} for dep in deps_list if dep])
        except FileNotFoundError:
            raise
        except Exception as e:
            raise Exception(f"Ошибка при чтении файла {file_path}: {e}")
        
        return dependencies

class DependencyGraph:
    def __init__(self, fetcher, max_depth=10, filter_substring=None):
        self.fetcher = fetcher
        self.max_depth = max_depth
        self.filter_substring = filter_substring
        self.graph = {}
        self.visited = set()
    
    def build_graph(self, root_package, root_version):
        """Строит граф зависимостей используя BFS"""
        queue = deque()
        # Храним путь вместе с каждым элементом: (package, version, depth, path)
        # path - это кортеж из package_key узлов от корня до текущего
        queue.append((root_package, root_version, 0, ()))
        self.graph = {}
        self.visited = set()  # Для отслеживания обработанных узлов
        
        while queue:
            current_package, current_version, depth, path = queue.popleft()
            
            if depth > self.max_depth:
                continue
            if self.filter_substring and self.filter_substring in current_package:
                continue
            
            package_key = f"{current_package}@{current_version}"
            
            # Проверка циклических зависимостей - проверяем только путь текущего обхода
            if package_key in path:
                # Это настоящий цикл - пакет встречается дважды в одном пути
                cycle_path = list(path) + [package_key]
                print(f"Обнаружена циклическая зависимость: {' -> '.join(cycle_path)}")
                continue
            
            # Если узел уже был обработан, пропускаем (но это не цикл, а просто пересечение путей)
            if package_key in self.visited:
                continue
                
            self.visited.add(package_key)
            
            try:
                dependencies = self.fetcher.get_package_dependencies(current_package, current_version)
                self.graph[package_key] = dependencies
                
                # Создаем новый путь, включая текущий узел
                new_path = path + (package_key,)
                
                for dep in dependencies:
                    if depth + 1 <= self.max_depth:
                        # Парсим версию из диапазона
                        version_range = dep.get('version_range', '')
                        # Простое извлечение минимальной версии из диапазона
                        if version_range:
                            match = re.match(r'[\[\(]([0-9.]+)', version_range)
                            if match:
                                dep_version = match.group(1)
                            else:
                                dep_version = '1.0.0'
                        else:
                            dep_version = '1.0.0'
                        queue.append((dep['id'], dep_version, depth + 1, new_path))
                        
            except Exception as e:
                print(f"Ошибка при получении зависимостей для {package_key}: {e}")
                self.graph[package_key] = []
    
    def find_reverse_dependencies(self, target_package):
        """Находит обратные зависимости - пакеты, которые зависят от target_package"""
        reverse_deps = []
        
        for package, dependencies in self.graph.items():
            package_name = package.split('@')[0]
            
            # Проверяем, зависит ли текущий пакет от целевого
            for dep in dependencies:
                if dep['id'] == target_package:
                    reverse_deps.append(package_name)
                    break
        
        return reverse_deps
    
    def print_graph(self):
        """Выводит граф зависимостей"""
        print("\nГраф зависимостей:")
        for package, dependencies in self.graph.items():
            print(f"{package}:")
            for dep in dependencies:
                print(f"  └── {dep['id']} {dep['version_range']}")
    
    def print_reverse_dependencies(self, target_package):
        """Выводит обратные зависимости"""
        reverse_deps = self.find_reverse_dependencies(target_package)
        
        print(f"\nОбратные зависимости для {target_package}:")
        if reverse_deps:
            for dep in reverse_deps:
                print(f"  └── {dep}")
        else:
            print("  Обратные зависимости не найдены")

class Config:
    def __init__(self):
        self.parser = argparse.ArgumentParser(description='Dependency Graph Visualizer')
        self._setup_arguments()
        self.args = None
    
    def _setup_arguments(self):
        self.parser.add_argument('--package', required=True, help='Имя анализируемого пакета')
        self.parser.add_argument('--source', required=True, help='URL репозитория или путь к файлу')
        self.parser.add_argument('--test-mode', action='store_true', help='Режим тестового репозитория')
        self.parser.add_argument('--version', required=True, help='Версия пакета')
        self.parser.add_argument('--ascii-tree', action='store_true', help='Вывод в формате ASCII-дерева')
        self.parser.add_argument('--max-depth', type=int, default=10, help='Максимальная глубина анализа')
        self.parser.add_argument('--filter', help='Подстрока для фильтрации пакетов')
        # Новый параметр для Этапа 4
        self.parser.add_argument('--reverse', help='Найти обратные зависимости для указанного пакета')
    
    def parse_args(self):
        try:
            self.args = self.parser.parse_args()
            self._validate_args()
            return self.args
        except Exception as e:
            print(f"Ошибка: {e}")
            sys.exit(1)
    
    def _validate_args(self):
        if self.args.max_depth <= 0:
            raise ValueError("Максимальная глубина должна быть положительным числом")
        if not self.args.version:
            raise ValueError("Версия пакета не может быть пустой")

def main():
    config = Config()
    args = config.parse_args()
    
    print("Параметры конфигурации:")
    for key, value in vars(args).items():
        print(f"{key}: {value}")
    
    print("\n" + "="*50)
    
    if args.test_mode:
        if args.source.endswith('.txt'):
            # Преобразуем путь в абсолютный для надежности
            source_path = args.source
            
            # Если путь относительный, делаем его относительно текущей рабочей директории
            if not os.path.isabs(source_path):
                # Пробуем несколько вариантов:
                current_dir = os.getcwd()
                possible_paths = [
                    os.path.join(current_dir, source_path),  # Указанный путь как есть
                    os.path.join(current_dir, 'src', os.path.basename(source_path)),  # В подпапке src
                    os.path.join(current_dir, os.path.basename(source_path))  # Только имя файла
                ]
                
                # Ищем первый существующий файл
                found = False
                for path in possible_paths:
                    if os.path.exists(path) and os.path.isfile(path):
                        source_path = os.path.abspath(path)
                        found = True
                        break
                
                if not found:
                    # Если не нашли, используем первый вариант (исходный путь)
                    source_path = os.path.abspath(os.path.join(current_dir, source_path))
            
            base_url = f"file://{source_path}"
            print(f"РЕЖИМ ТЕСТИРОВАНИЯ: чтение из файла {source_path}")
        else:
            base_url = "test://local/"
            print("РЕЖИМ ТЕСТИРОВАНИЯ: использование тестовых данных")
    else:
        base_url = "https://api.nuget.org/v3/registration5-gz-semver2/"
    
    fetcher = DependencyFetcher(base_url)
    graph_builder = DependencyGraph(fetcher, args.max_depth, args.filter)
    
    try:
        print(f"Построение графа зависимостей для {args.package} {args.version}...")
        graph_builder.build_graph(args.package, args.version)
        
        # Этап 4: Вывод обратных зависимостей если указан --reverse
        if args.reverse:
            graph_builder.print_reverse_dependencies(args.reverse)
        else:
            graph_builder.print_graph()
        
    except Exception as e:
        print(f"Ошибка при построении графа: {e}")

if __name__ == "__main__":
    main()