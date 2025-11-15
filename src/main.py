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
            #Тестовоый режим - имитируем данные
            if hasattr(self, 'test_data'):
                return self._get_test_dependencies(package_name, version)
            
            # Реальный NuGet API
            package_url = f"{self.base_url}{package_name.lower()}/index.json"
            response = self.session.get(package_url)
            response.raise_for_status()
            
            package_data = response.json()
            
            for version_entry in package_data.get('versions', []):
                if version_entry['version'] == version:
                    version_url = version_entry['@id']
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
        catalog_entry = version_data.get('catalogEntry', {})
        dependency_groups = catalog_entry.get('dependencyGroups', [])
        
        for group in dependency_groups:
            for dep in group.get('dependencies', []):
                dependencies.append({
                    'id': dep['id'],
                    'version_range': dep.get('range', '')
                })
        
        return dependencies
    
    def set_test_data(self, test_data):
        """Устанавливает тестовые данные для режима тестирования"""
        self.test_data = test_data
    
    def _get_test_dependencies(self, package_name, version):
        """Получает зависимости из тестовых данных"""
        package_key = f"{package_name}_{version}"
        return self.test_data.get(package_key, [])

class DependencyGraph:
    def __init__(self, fetcher, max_depth, filter_substring):
        self.fetcher = fetcher
        self.max_depth = max_depth
        self.filter_substring = filter_substring
        self.graph = {}
        self.visited = set()
    
    def build_graph(self, root_package, root_version):
        """Строит граф зависимостей с помощью BFS"""
        queue = deque()
        queue.append((root_package, root_version, 0))
        self.visited.add(f"{root_package}_{root_version}")
        
        while queue:
            current_package, current_version, depth = queue.popleft()
            
            # Проверяем максимальную глубину
            if depth >= self.max_depth:
                continue
            
            # Получаем зависимости текущего пакета
            try:
                dependencies = self.fetcher.get_package_dependencies(current_package, current_version)
                
                # Фильтруем зависимости
                filtered_deps = []
                for dep in dependencies:
                    if self.filter_substring and self.filter_substring in dep['id']:
                        continue  # Пропускаем пакеты с фильтруемой подстрокой
                    filtered_deps.append(dep)
                
                # Добавляем в граф
                current_key = f"{current_package}_{current_version}"
                self.graph[current_key] = filtered_deps
                
                # Добавляем зависимости в очередь для дальнейшего обхода
                for dep in filtered_deps:
                    dep_key = f"{dep['id']}_{self._extract_version(dep['version_range'])}"
                    
                    # Проверяем циклические зависимости
                    if dep_key not in self.visited:
                        self.visited.add(dep_key)
                        queue.append((dep['id'], self._extract_version(dep['version_range']), depth + 1))
                    else:
                        print(f"Обнаружена циклическая зависимость: {dep_key}")
                        
            except Exception as e:
                print(f"Ошибка при получении зависимостей для {current_package}: {e}")
    
   def _extract_version(self, version_range):
    """Извлекает версию из диапазона (упрощенная версия)"""
    if not version_range or version_range == "(, )":
        return "1.0"  # Версия по умолчанию без .0
    import re
    match = re.search(r'(\d+\.\d+)', version_range)  # Ищем только X.Y
    return match.group(1) if match else "1.0"
    
    def get_graph(self):
        return self.graph
    
    def print_graph(self):
        """Выводит граф в читаемом формате"""
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

def load_test_data(file_path):
    """Загружает тестовые данные из файла"""
    test_data = {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and '->' in line:
                    parts = line.split('->')
                    package_info = parts[0].strip()
                    dependencies = []
                    
                    if len(parts) > 1:
                        for dep in parts[1].split(','):
                            dep = dep.strip()
                            if dep:
                                dependencies.append({'id': dep, 'version_range': '1.0.0'})
                    
                    test_data[package_info] = dependencies
        return test_data
    except Exception as e:
        raise Exception(f"Ошибка загрузки тестового файла: {e}")

def main():
    config = Config()
    args = config.parse_args()
    
    # Вывод параметров (этап 1)
    print("Параметры конфигурации:")
    for key, value in vars(args).items():
        print(f"{key}: {value}")
    
    print("\n" + "="*50)
    
    # Настройка зависимости от режима
    if args.test_mode:
        # Режим тестирования - используем файл
        print("Режим тестирования активирован")
        try:
            test_data = load_test_data(args.source)
            fetcher = DependencyFetcher("")
            fetcher.set_test_data(test_data)
        except Exception as e:
            print(f"Ошибка: {e}")
            return
    else:
        # Режим реального репозитория
        fetcher = DependencyFetcher("https://api.nuget.org/v3/registration5-gz-semver2/")
    
    # Этап 2: Получение прямых зависимостей
    try:
        print(f"Получение зависимостей для {args.package} версии {args.version}...")
        dependencies = fetcher.get_package_dependencies(args.package, args.version)
        
        print(f"\nПрямые зависимости пакета {args.package} {args.version}:")
        if dependencies:
            for dep in dependencies:
                print(f"  - {dep['id']} {dep['version_range']}")
        else:
            print("  Зависимости не найдены")
    except Exception as e:
        print(f"Ошибка при получении зависимостей: {e}")
        return
    
    print("\n" + "="*50)
    
    # Этап 3: Построение полного графа BFS
    print("Построение полного графа зависимостей...")
    
    graph_builder = DependencyGraph(fetcher, args.max_depth, args.filter)
    graph_builder.build_graph(args.package, args.version)
    
    # Вывод результата
    graph_builder.print_graph()

if __name__ == "__main__":
    main()