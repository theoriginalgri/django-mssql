#!/usr/bin/env python
from __future__ import division

import logging
import os
import shutil
import subprocess
import sys
import tempfile
import warnings

import django
from django import contrib
from django.utils.deprecation import RemovedInDjango18Warning, RemovedInDjango19Warning
from django.utils._os import upath
from django.utils import six

CONTRIB_MODULE_PATH = 'django.contrib'

TEST_TEMPLATE_DIR = 'templates'

DJANGO_RUNTESTS_DIR = os.path.abspath(os.path.join(os.path.dirname(upath(django.__file__)), '..', 'tests'))
RUNTESTS_DIR = os.path.abspath(os.path.dirname(upath(__file__)))
CONTRIB_DIR = os.path.dirname(upath(contrib.__file__))

TEMP_DIR = tempfile.mkdtemp(prefix='django_mssql_')
os.environ['DJANGO_TEST_TEMP_DIR'] = TEMP_DIR

MSSQL_DIR = os.path.abspath(os.path.join(RUNTESTS_DIR, '..'))

if MSSQL_DIR not in sys.path:
    sys.path.append(MSSQL_DIR)
if DJANGO_RUNTESTS_DIR not in sys.path:
    sys.path.append(DJANGO_RUNTESTS_DIR)

SUBDIRS_TO_SKIP = [
    TEST_TEMPLATE_DIR,
    CONTRIB_DIR,
    'test_main',
]

DJANGO_TESTS_TO_INCLUDE = [
    'aggregation',
    'aggregation_regress',
    'backends',
    'basic',
    'bulk_create',
    'cache',
    'commands_sql',
    'custom_columns',
    'custom_columns_regress',
    'custom_managers',
    'custom_managers_regress',
    'custom_methods',
    'custom_pk',
    'datatypes',
    'dates',
    'datetimes',
    'db_typecasts',
    'defer',
    'defer_regress',
    'delete',
    'delete_regress',
    'expressions',
    'expressions_regress',
    'generic_relations',
    'generic_relations_regress',
    'get_object_or_404',
    'get_or_create',
    'get_or_create_regress',
    'initial_sql_regress',
    'inspectdb',
    'introspection',
    'known_related_objects',
    'lookup',
    'max_lengths',
    'model_inheritance',
    'model_inheritance_regress',
    'model_inheritance_same_model_name',
    'model_inheritance_select_related',
    'model_regress',
    'multiple_databases',
    'mutually_referential',
    'nested_foreign_keys',
    'null_fk',
    'null_fk_ordering',
    'null_queries',
    'ordering',
    'pagination',
    'prefetch_related',
    'queries',
    'raw_query',
    'reserved_names',
    'reverse_lookup',
    'reverse_single_related',
    'schema',
    'select_for_update',
    'select_related',
    'select_related_onetoone',
    'select_related_regress',
    'string_lookup',
    'tablespaces',
    'timezones',
    'transactions',
    'transactions_regress',
    'update_only_fields',
]

ALWAYS_INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'django.contrib.sessions',
    'sqlserver_ado',
    'sqlserver_ado.sql_app',
]

ALWAYS_MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
)


def get_test_modules():
    test_dirs = [
        (None, RUNTESTS_DIR),
        (None, DJANGO_RUNTESTS_DIR),
    ]

    modules = []
    for modpath, dirpath in test_dirs:
        for f in os.listdir(dirpath):
            if ('.' in f or
                # Python 3 byte code dirs (PEP 3147)
                f == '__pycache__' or
                f.startswith('sql') or
                os.path.basename(f) in SUBDIRS_TO_SKIP or
                os.path.isfile(f)):
                continue
            if dirpath.startswith(DJANGO_RUNTESTS_DIR) and os.path.basename(f) not in DJANGO_TESTS_TO_INCLUDE:
                continue
            modules.append((modpath, f))
    return modules

def get_installed():
    from django.db.models.loading import get_apps
    return [app.__name__.rsplit('.', 1)[0] for app in get_apps() if not app.__name__.startswith('django.contrib')]

def setup(verbosity, test_labels):
    from django.apps import apps
    from django.conf import settings
    from django.test import TransactionTestCase, TestCase

    print("Testing against Django installed in '%s'" % os.path.dirname(django.__file__))

    # Force declaring available_apps in TransactionTestCase for faster tests.
    def no_available_apps(self):
        raise Exception("Please define available_apps in TransactionTestCase "
                        "and its subclasses.")
    TransactionTestCase.available_apps = property(no_available_apps)
    TestCase.available_apps = None


    state = {
        'INSTALLED_APPS': settings.INSTALLED_APPS,
        'ROOT_URLCONF': getattr(settings, "ROOT_URLCONF", ""),
        'TEMPLATE_DIRS': settings.TEMPLATE_DIRS,
        'LANGUAGE_CODE': settings.LANGUAGE_CODE,
        'STATIC_URL': settings.STATIC_URL,
        'STATIC_ROOT': settings.STATIC_ROOT,
        'MIDDLEWARE_CLASSES': settings.MIDDLEWARE_CLASSES,
    }

    # Redirect some settings for the duration of these tests.
    settings.INSTALLED_APPS = ALWAYS_INSTALLED_APPS
    settings.ROOT_URLCONF = 'urls'
    settings.STATIC_URL = '/static/'
    settings.STATIC_ROOT = os.path.join(TEMP_DIR, 'static')
    settings.TEMPLATE_DIRS = (os.path.join(RUNTESTS_DIR, TEST_TEMPLATE_DIR),)
    settings.LANGUAGE_CODE = 'en'
    settings.SITE_ID = 1
    settings.MIDDLEWARE_CLASSES = ALWAYS_MIDDLEWARE_CLASSES
    # Ensure the middleware classes are seen as overridden otherwise we get a compatibility warning.
    settings._explicit_settings.add('MIDDLEWARE_CLASSES')
    settings.MIGRATION_MODULES = {
        # these 'tests.migrations' modules don't actually exist, but this lets
        # us skip creating migrations for the test models.
        'auth': 'django.contrib.auth.tests.migrations',
        'contenttypes': 'django.contrib.contenttypes.tests.migrations',
    }

    if verbosity > 0:
        # Ensure any warnings captured to logging are piped through a verbose
        # logging handler.  If any -W options were passed explicitly on command
        # line, warnings are not captured, and this has no effect.
        logger = logging.getLogger('py.warnings')
        handler = logging.StreamHandler()
        logger.addHandler(handler)

    warnings.filterwarnings(
        'ignore',
        'django.contrib.comments is deprecated and will be removed before Django 1.8.',
        RemovedInDjango18Warning
    )
    warnings.filterwarnings(
        'ignore',
        'Model class django.contrib.comments.models.* Django 1.9.',
        RemovedInDjango19Warning
    )
    # Load all the ALWAYS_INSTALLED_APPS.
    django.setup()


    # Load all the test model apps.
    test_modules = get_test_modules()

    # Reduce given test labels to just the app module path
    test_labels_set = set()
    for label in test_labels:
        bits = label.split('.')
        if bits[:2] == ['django', 'contrib']:
            bits = bits[:3]
        else:
            bits = bits[:1]
        test_labels_set.add('.'.join(bits))

    installed_app_names = set(get_installed())
    for modpath, module_name in test_modules:
        if modpath:
            module_label = '.'.join([modpath, module_name])
        else:
            module_label = module_name
        # if the module (or an ancestor) was named on the command line, or
        # no modules were named (i.e., run all), import
        # this module and add it to INSTALLED_APPS.
        if not test_labels:
            module_found_in_labels = True
        else:
            module_found_in_labels = any(
                # exact match or ancestor match
                module_label == label or module_label.startswith(label + '.')
                for label in test_labels_set)

        if module_found_in_labels and module_label not in installed_app_names:
            if verbosity >= 2:
                print("Importing application %s" % module_name)
            settings.INSTALLED_APPS.append(module_label)

    apps.set_installed_apps(settings.INSTALLED_APPS)

    return state


def teardown(state):
    from django.conf import settings

    try:
        # Removing the temporary TEMP_DIR. Ensure we pass in unicode
        # so that it will successfully remove temp trees containing
        # non-ASCII filenames on Windows. (We're assuming the temp dir
        # name itself does not contain non-ASCII characters.)
        shutil.rmtree(six.text_type(TEMP_DIR))
    except OSError:
        print('Failed to remove temp directory: %s' % TEMP_DIR)

    # Restore the old settings.
    for key, value in state.items():
        setattr(settings, key, value)


def django_tests(verbosity, interactive, failfast, test_labels):
    from django.conf import settings
    state = setup(verbosity, test_labels)
    extra_tests = []

    # Run the test suite, including the extra validation tests.
    from django.test.utils import get_runner
    if not hasattr(settings, 'TEST_RUNNER'):
        settings.TEST_RUNNER = 'django.test.runner.DiscoverRunner'
    TestRunner = get_runner(settings)

    test_runner = TestRunner(
        verbosity=verbosity,
        interactive=interactive,
        failfast=failfast,
    )
    # Catch warnings thrown in test DB setup -- remove in Django 1.9
    with warnings.catch_warnings():
        warnings.filterwarnings(
            'ignore',
            "Custom SQL location '<app_label>/models/sql' is deprecated, "
            "use '<app_label>/sql' instead.",
            RemovedInDjango19Warning
        )
        warnings.filterwarnings(
            'ignore',
            'initial_data fixtures are deprecated. Use data migrations instead.',
            RemovedInDjango19Warning
        )
        warnings.filterwarnings(
            'ignore',
            'IPAddressField has been deprecated. Use GenericIPAddressField instead.',
            RemovedInDjango19Warning
        )
        failures = test_runner.run_tests(
            test_labels or get_installed(), extra_tests=extra_tests)

    teardown(state)
    return failures


def bisect_tests(bisection_label, options, test_labels):
    state = setup(int(options.verbosity), test_labels)

    test_labels = test_labels or get_installed()

    print('***** Bisecting test suite: %s' % ' '.join(test_labels))

    # Make sure the bisection point isn't in the test list
    # Also remove tests that need to be run in specific combinations
    for label in [bisection_label, 'model_inheritance_same_model_name']:
        try:
            test_labels.remove(label)
        except ValueError:
            pass

    subprocess_args = [
        sys.executable, upath(__file__), '--settings=%s' % options.settings]
    if options.failfast:
        subprocess_args.append('--failfast')
    if options.verbosity:
        subprocess_args.append('--verbosity=%s' % options.verbosity)
    if not options.interactive:
        subprocess_args.append('--noinput')

    iteration = 1
    while len(test_labels) > 1:
        midpoint = len(test_labels) // 2
        test_labels_a = test_labels[:midpoint] + [bisection_label]
        test_labels_b = test_labels[midpoint:] + [bisection_label]
        print('***** Pass %da: Running the first half of the test suite' % iteration)
        print('***** Test labels: %s' % ' '.join(test_labels_a))
        failures_a = subprocess.call(subprocess_args + test_labels_a)

        print('***** Pass %db: Running the second half of the test suite' % iteration)
        print('***** Test labels: %s' % ' '.join(test_labels_b))
        print('')
        failures_b = subprocess.call(subprocess_args + test_labels_b)

        if failures_a and not failures_b:
            print("***** Problem found in first half. Bisecting again...")
            iteration = iteration + 1
            test_labels = test_labels_a[:-1]
        elif failures_b and not failures_a:
            print("***** Problem found in second half. Bisecting again...")
            iteration = iteration + 1
            test_labels = test_labels_b[:-1]
        elif failures_a and failures_b:
            print("***** Multiple sources of failure found")
            break
        else:
            print("***** No source of failure found... try pair execution (--pair)")
            break

    if len(test_labels) == 1:
        print("***** Source of error: %s" % test_labels[0])
    teardown(state)


def paired_tests(paired_test, options, test_labels):
    state = setup(int(options.verbosity), test_labels)

    test_labels = test_labels or get_installed()

    print('***** Trying paired execution')

    # Make sure the constant member of the pair isn't in the test list
    # Also remove tests that need to be run in specific combinations
    for label in [paired_test, 'model_inheritance_same_model_name']:
        try:
            test_labels.remove(label)
        except ValueError:
            pass

    subprocess_args = [
        sys.executable, upath(__file__), '--settings=%s' % options.settings]
    if options.failfast:
        subprocess_args.append('--failfast')
    if options.verbosity:
        subprocess_args.append('--verbosity=%s' % options.verbosity)
    if not options.interactive:
        subprocess_args.append('--noinput')

    for i, label in enumerate(test_labels):
        print('***** %d of %d: Check test pairing with %s' % (
              i + 1, len(test_labels), label))
        failures = subprocess.call(subprocess_args + [label, paired_test])
        if failures:
            print('***** Found problem pair with %s' % label)
            return

    print('***** No problem pair found')
    teardown(state)


if __name__ == "__main__":
    from optparse import OptionParser
    usage = "%prog [options] [module module module ...]"
    parser = OptionParser(usage=usage)
    parser.add_option(
        '-v', '--verbosity', action='store', dest='verbosity', default='1',
        type='choice', choices=['0', '1', '2', '3'],
        help='Verbosity level; 0=minimal output, 1=normal output, 2=all '
             'output')
    parser.add_option(
        '--noinput', action='store_false', dest='interactive', default=True,
        help='Tells Django to NOT prompt the user for input of any kind.')
    parser.add_option(
        '--failfast', action='store_true', dest='failfast', default=False,
        help='Tells Django to stop running the test suite after first failed '
             'test.')
    parser.add_option(
        '--settings',
        help='Python path to settings module, e.g. "myproject.settings". If '
             'this isn\'t provided, the DJANGO_SETTINGS_MODULE environment '
             'variable will be used.')
    parser.add_option(
        '--bisect', action='store', dest='bisect', default=None,
        help='Bisect the test suite to discover a test that causes a test '
             'failure when combined with the named test.')
    parser.add_option(
        '--pair', action='store', dest='pair', default=None,
        help='Run the test suite in pairs with the named test to find problem '
             'pairs.')
    parser.add_option(
        '--liveserver', action='store', dest='liveserver', default=None,
        help='Overrides the default address where the live server (used with '
             'LiveServerTestCase) is expected to run from. The default value '
             'is localhost:8081.')
    parser.add_option(
        '--selenium', action='store_true', dest='selenium',
        default=False,
        help='Run the Selenium tests as well (if Selenium is installed)')
    options, args = parser.parse_args()
    if options.settings:
        os.environ['DJANGO_SETTINGS_MODULE'] = options.settings
    else:
        if "DJANGO_SETTINGS_MODULE" not in os.environ:
            os.environ['DJANGO_SETTINGS_MODULE'] = 'test_sqlite'
        options.settings = os.environ['DJANGO_SETTINGS_MODULE']

    if options.liveserver is not None:
        os.environ['DJANGO_LIVE_TEST_SERVER_ADDRESS'] = options.liveserver

    if options.selenium:
        os.environ['DJANGO_SELENIUM_TESTS'] = '1'

    if options.bisect:
        bisect_tests(options.bisect, options, args)
    elif options.pair:
        paired_tests(options.pair, options, args)
    else:
        failures = django_tests(int(options.verbosity), options.interactive,
                                options.failfast, args)
        if failures:
            sys.exit(bool(failures))
