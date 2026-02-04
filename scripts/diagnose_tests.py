import unittest
import os

loader = unittest.TestLoader()
suite = loader.discover('tests')

print('Discovered tests suite:', suite)

# Count tests
count = suite.countTestCases()
print('Total test cases discovered:', count)

# Walk and print test module names
for s in suite:
    print('Suite item:', s)
    for t in s:
        print(' -', t)

# Try to load all test module names
print('\nAttempting to load modules explicitly:')
for root, dirs, files in os.walk('tests'):
    for f in files:
        if f.startswith('test') and f.endswith('.py'):
            path = os.path.join(root, f)
            modname = os.path.splitext(os.path.relpath(path, 'tests'))[0].replace(os.sep, '.')
            print(modname)
            try:
                __import__('tests.' + modname)
                print('  imported')
            except Exception as e:
                import traceback; traceback.print_exc()
