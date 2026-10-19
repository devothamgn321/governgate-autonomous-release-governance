"""Validate pytest's structured report against fixed consumer test functions."""
import xml.etree.ElementTree as ET
from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException


def summarize_junit(report, expected):
    """Require nonzero completed tests and coverage of every expected test name."""
    try:
        root = SafeET.parse(report).getroot()
    except (OSError, ET.ParseError, DefusedXmlException):
        return {'status': 'INCONCLUSIVE', 'tests': 0, 'expected_tests': len(expected),
                'failures': 0, 'errors': 0, 'missing_tests': sorted(name for _, name in expected)}
    cases = list(root.iter('testcase'))
    failures = sum(len(case.findall('failure')) for case in cases)
    errors = sum(len(case.findall('error')) for case in cases)
    skipped = sum(len(case.findall('skipped')) for case in cases)
    seen = set()
    for case in cases:
        name = case.attrib.get('name', '').split('[', 1)[0]
        classname = case.attrib.get('classname', '').replace('::', '.')
        seen.add((classname, name))
    # GitLab's pinned consumer trees use pytest's module name as classname.
    missing = sorted(f'{module}::{name}' for module, name in expected
                     if (module, name) not in seen
                     and not any(found_name == name and found_module.endswith(module)
                                 for found_module, found_name in seen))
    if not cases or not expected or missing:
        status = 'INCONCLUSIVE'
    elif failures or errors:
        status = 'FAIL'
    elif len(cases) <= skipped:
        status = 'INCONCLUSIVE'
    else:
        status = 'PASS'
    return {'status': status, 'tests': len(cases), 'expected_tests': len(expected),
            'failures': failures, 'errors': errors, 'missing_tests': missing}
