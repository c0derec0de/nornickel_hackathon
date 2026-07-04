"""Доменная онтология горно-металлургической R&D-области."""

# Типы сущностей (метки узлов в Neo4j)
ENTITY_TYPES = [
    "Material",     # никель, медь, гипс, сульфаты, католит
    "Process",      # выщелачивание, электроэкстракция, взвешенная плавка
    "Equipment",    # ванна электроэкстракции, диафрагменная ячейка, ПВП
    "Property",     # коррозионная стойкость, выход металла, сухой остаток
    "Condition",    # числовое ограничение/режим: сульфаты<=300 мг/л, T 60-80C
    "Experiment",   # протокол опыта
    "Publication",  # статья, отчёт, патент, диссертация
    "Expert",       # автор / носитель компетенции
    "Facility",     # лаборатория / фабрика / установка
    "Finding",      # подтверждённый вывод / эффект
    "Geography",    # РФ / зарубеж / регион
]

# Типы связей
RELATION_TYPES = [
    "USES_MATERIAL",        # Process/Experiment -> Material
    "OPERATES_AT_CONDITION",# Process/Experiment -> Condition
    "PRODUCES_OUTPUT",      # Process/Experiment -> Finding/Property
    "HAS_PROPERTY",         # Material/Process -> Property
    "USES_EQUIPMENT",       # Process/Experiment -> Equipment
    "DESCRIBED_IN",         # * -> Publication
    "VALIDATED_BY",         # Finding -> Experiment/Publication
    "AUTHORED_BY",          # Publication/Experiment -> Expert
    "EXPERT_IN",            # Expert -> Process/Material/Property
    "PERFORMED_AT",         # Experiment -> Facility
    "APPLIES_TO",           # Process/Finding -> Material
    "CONTRADICTS",          # Finding -> Finding
    "LOCATED_IN",           # Facility/Publication -> Geography
]

# Нормализация синонимов -> канон
SYNONYMS = {
    "electrowinning": "электроэкстракция",
    "electroextraction": "электроэкстракция",
    "пвп": "печь взвешенной плавки",
    "fluidized bed furnace": "печь взвешенной плавки",
    "flash smelting furnace": "печь взвешенной плавки",
    "heap leaching": "кучное выщелачивание",
    "catholyte": "католит",
    "desalination": "обессоливание воды",
}


def canonical(name: str) -> str:
    key = (name or "").strip().lower()
    return SYNONYMS.get(key, (name or "").strip())
