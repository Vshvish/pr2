#!/usr/bin/env python3
import argparse
import sys
import requests
import json
from urllib.parse import urljoin
from collections import deque

class DependencyFetcher:
    def __init__(self, base_url):
        self.base_url = base_url
        self.session = requests.Session()
    
    def get_package_dependencies(self, package_name, version):
        """Получает прямые зависимости пакета"""
        try:
            # Для тестового режима - заглушка
            if "test" in self.base_url:
                return self._get_test_dependencies(package_name, version)
                
            # Реальный NuGet API
            package_url = f"{self.base_url}{package_name.lower()}/index.json"
            response = self.session.get(package_url)
            response.raise_for_status()
            
            package_data = response.json()
            
            # NuGet API v3 использует вложенную структуру items
            # Обходим все элементы items, включая пагинацию
            items = package_data.get('items', [])
            pages_to_check = []
            
            for item in items:
                # Каждый item может содержать items с версиями или ссылку на другую страницу
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
                    # или листовая версия
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
            # Если catalogEntry нет на верхнем уровне, возможно это прямая структура
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
        """Заглушка для тестового режима - зависимости по буквам"""
        # Простая логика: A -> B,C; B -> D; C -> E и т.д.
        test_graph = {
            'A': ['B', 'C'],
            'B': ['D'], 
            'C': ['E', 'F'],
            'D': ['G'],
            'E': ['B'],  # Цикл E -> B -> D -> G
            'F': [],
            'G': []
        }
        return [{'id': dep, 'version_range': '1.0.0'} for dep in test_graph.get(package_name, [])]
    
    def get_package_versions(self, package_name):
        """Получает список доступных версий пакета"""
        # Для тестового режима не получаем версии из API
        if "test" in self.base_url:
            return ["1.0.0"]  # Возвращаем тестовую версию
        
        try:
            package_url = f"{self.base_url}{package_name.lower()}/index.json"
            response = self.session.get(package_url)
            response.raise_for_status()
            package_data = response.json()
            
            versions = []
            items = package_data.get('items', [])
            pages_to_check = []
            
            for item in items:
                version_items = item.get('items', [])
                if version_items:
                    for version_entry in version_items:
                        catalog_entry = version_entry.get('catalogEntry', {})
                        if 'version' in catalog_entry:
                            versions.append(catalog_entry['version'])
                else:
                    if 'catalogEntry' in item:
                        catalog_entry = item['catalogEntry']
                        if 'version' in catalog_entry:
                            versions.append(catalog_entry['version'])
                    item_url = item.get('@id')
                    if item_url:
                        pages_to_check.append(item_url)
            
            # Проверяем дополнительные страницы
            for page_url in pages_to_check:
                page_response = self.session.get(page_url)
                page_response.raise_for_status()
                page_data = page_response.json()
                page_items = page_data.get('items', [])
                for version_entry in page_items:
                    catalog_entry = version_entry.get('catalogEntry', {})
                    if 'version' in catalog_entry:
                        versions.append(catalog_entry['version'])
            
            return sorted(versions, reverse=True)  # Возвращаем версии от новых к старым
        except Exception:
            return []
    
    def parse_version_range(self, version_range):
        """Парсит версионный диапазон и возвращает подходящую версию"""
        if not version_range or version_range == "":
            return None
        
        # Убираем пробелы
        version_range = version_range.strip()
        
        # Парсим диапазоны вида [4.3.0, ), (4.3.0, ), [4.3.0, 5.0.0) и т.д.
        import re
        
        # Паттерны для парсинга диапазонов
        # [4.3.0, ) или (4.3.0, ) - минимальная версия
        match = re.match(r'[\[\(]([0-9.]+)(?:\s*,\s*[\)\[])?', version_range)
        if match:
            min_version = match.group(1)
            return min_version
        
        # [4.3.0] - точная версия
        match = re.match(r'\[([0-9.]+)\]', version_range)
        if match:
            return match.group(1)
        
        # 4.3.0 - точная версия без скобок
        match = re.match(r'^([0-9.]+)$', version_range)
        if match:
            return match.group(1)
        
        return None

class DependencyGraph:
    def __init__(self, fetcher, max_depth=10, filter_substring=None):
        self.fetcher = fetcher
        self.max_depth = max_depth
        self.filter_substring = filter_substring
        self.graph = {}
        self.visited = set()
        self.version_cache = {}  # Кэш для версий пакетов
    
    def _get_dependency_version(self, package_name, version_range):
        """Получает конкретную версию для зависимости на основе версионного диапазона"""
        # Парсим минимальную версию из диапазона
        min_version = self.fetcher.parse_version_range(version_range)
        if not min_version:
            # Если не удалось распарсить, пробуем получить последнюю версию пакета
            return self._get_latest_version(package_name)
        
        # Проверяем кэш
        cache_key = package_name.lower()
        if cache_key not in self.version_cache:
            self.version_cache[cache_key] = self.fetcher.get_package_versions(package_name)
        
        available_versions = self.version_cache[cache_key]
        if not available_versions:
            return min_version  # Возвращаем минимальную версию, если список пуст
        
        # Ищем подходящую версию (>= минимальной)
        # Берем первую доступную версию >= минимальной
        for v in available_versions:
            # Простое сравнение: если версия >= минимальной
            if v == min_version or self._compare_versions(v, min_version) >= 0:
                return v
        
        # Если не нашли подходящую, возвращаем последнюю доступную
        return available_versions[0] if available_versions else min_version
    
    def _compare_versions(self, v1, v2):
        """Простое сравнение версий (v1 >= v2 возвращает >= 0)"""
        try:
            parts1 = [int(x) for x in v1.split('.')]
            parts2 = [int(x) for x in v2.split('.')]
            # Дополняем нулями до одинаковой длины
            max_len = max(len(parts1), len(parts2))
            parts1 += [0] * (max_len - len(parts1))
            parts2 += [0] * (max_len - len(parts2))
            for p1, p2 in zip(parts1, parts2):
                if p1 > p2:
                    return 1
                elif p1 < p2:
                    return -1
            return 0
        except:
            # Если не удалось распарсить, используем строковое сравнение
            return 1 if v1 >= v2 else -1
    
    def _get_latest_version(self, package_name):
        """Получает последнюю версию пакета"""
        cache_key = package_name.lower()
        if cache_key not in self.version_cache:
            self.version_cache[cache_key] = self.fetcher.get_package_versions(package_name)
        
        available_versions = self.version_cache[cache_key]
        return available_versions[0] if available_versions else "1.0.0"
    
    def build_graph(self, root_package, root_version):
        """Строит граф зависимостей используя BFS"""
        queue = deque()
        # Храним путь вместе с каждым элементом: (package, version, depth, path)
        # path - это кортеж из package_key узлов от корня до текущего
        queue.append((root_package, root_version, 0, ()))  
        self.graph = {}
        self.visited = set()  # Для отслеживания обработанных узлов (чтобы не обрабатывать повторно)
        
        while queue:
            current_package, current_version, depth, path = queue.popleft()
            
            # Пропускаем если превышена глубина или пакет отфильтрован
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
                # Получаем зависимости текущего пакета
                dependencies = self.fetcher.get_package_dependencies(current_package, current_version)
                self.graph[package_key] = dependencies
                
                # Создаем новый путь, включая текущий узел
                new_path = path + (package_key,)
                
                # Добавляем зависимости в очередь для дальнейшего обхода
                for dep in dependencies:
                    if depth + 1 <= self.max_depth:
                        # Получаем конкретную версию из диапазона
                        dep_version = self._get_dependency_version(dep['id'], dep['version_range'])
                        queue.append((dep['id'], dep_version, depth + 1, new_path))
                        
            except Exception as e:
                print(f"Ошибка при получении зависимостей для {package_key}: {e}")
                self.graph[package_key] = []
    
    def print_graph(self):
        """Выводит граф зависимостей"""
        print("\nГраф зависимостей:")
        for package, dependencies in self.graph.items():
            print(f"{package}:")
            for dep in dependencies:
                print(f"  └── {dep['id']} {dep['version_range']}")

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
    
    # Настраиваем источник данных в зависимости от режима
    if args.test_mode:
        base_url = "test://local/"
        print("РЕЖИМ ТЕСТИРОВАНИЯ: использование тестовых данных")
    else:
        base_url = "https://api.nuget.org/v3/registration5-gz-semver2/"
    
    fetcher = DependencyFetcher(base_url)
    graph_builder = DependencyGraph(fetcher, args.max_depth, args.filter)
    
    try:
        print(f"Построение графа зависимостей для {args.package} {args.version}...")
        graph_builder.build_graph(args.package, args.version)
        graph_builder.print_graph()
        
    except Exception as e:
        print(f"Ошибка при построении графа: {e}")

if __name__ == "__main__":
    main()