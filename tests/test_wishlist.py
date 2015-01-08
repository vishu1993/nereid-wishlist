# -*- coding: utf-8 -*-
'''

    nereid_wishlist test suite

    :copyright: (c) 2014-2015 by Openlabs Technologies & Consulting (P) Ltd.
    :license: GPLv3, see LICENSE for more details
'''
import unittest
from decimal import Decimal
from dateutil.relativedelta import relativedelta
import datetime

import pycountry
import trytond.tests.test_tryton
from trytond.tests.test_tryton import POOL, USER, DB_NAME, CONTEXT
from trytond.transaction import Transaction
from nereid.testing import NereidTestCase
from nereid import current_user


class TestWishlist(NereidTestCase):
    "Test Wishlist"

    def setUp(self):

        trytond.tests.test_tryton.install_module('nereid_wishlist')

        self.Language = POOL.get('ir.lang')
        self.NereidWebsite = POOL.get('nereid.website')
        self.Country = POOL.get('country.country')
        self.Subdivision = POOL.get('country.subdivision')
        self.Currency = POOL.get('currency.currency')
        self.NereidUser = POOL.get('nereid.user')
        self.User = POOL.get('res.user')
        self.Party = POOL.get('party.party')
        self.Company = POOL.get('company.company')
        self.Locale = POOL.get('nereid.website.locale')
        self.Uom = POOL.get('product.uom')
        self.Template = POOL.get('product.template')
        self.Location = POOL.get('stock.location')
        self.PriceList = POOL.get('product.price_list')
        self.SaleShop = POOL.get('sale.shop')

        self.templates = {
            'wishlists.jinja':
                '{{ current_user.wishlists| length }}',
            'wishlist.jinja':
                '{{ wishlist.name }}',
        }

    def _create_payment_term(self):
        """Create a simple payment term with all advance
        """
        PaymentTerm = POOL.get('account.invoice.payment_term')

        return PaymentTerm.create([{
            'name': 'Direct',
            'lines': [('create', [{'type': 'remainder'}])]
        }])

    def _create_pricelists(self):
        """
        Create the pricelists
        """
        # Setup the pricelists
        self.guest_pl_margin = Decimal('1.20')
        return self.PriceList.create([{
            'name': 'PL 2',
            'company': self.company.id,
            'lines': [
                ('create', [{
                    'formula': 'unit_price * %s' % self.guest_pl_margin
                }])
            ],
        }])[0]

    def _create_countries(self, count=5):
        """
        Create some sample countries and subdivisions
        """
        for country in list(pycountry.countries)[0:count]:
            countries = self.Country.create([{
                'name': country.name,
                'code': country.alpha2,
            }])
            try:
                divisions = pycountry.subdivisions.get(
                    country_code=country.alpha2
                )
            except KeyError:
                pass
            else:
                for subdivision in list(divisions)[0:count]:
                    self.Subdivision.create([{
                        'country': countries[0].id,
                        'name': subdivision.name,
                        'code': subdivision.code,
                        'type': subdivision.type.lower(),
                    }])

    def _create_coa_minimal(self, company):
        """Create a minimal chart of accounts
        """
        AccountTemplate = POOL.get('account.account.template')
        Account = POOL.get('account.account')

        account_create_chart = POOL.get(
            'account.create_chart', type="wizard")

        account_template, = AccountTemplate.search(
            [('parent', '=', None)]
        )

        session_id, _, _ = account_create_chart.create()
        create_chart = account_create_chart(session_id)
        create_chart.account.account_template = account_template
        create_chart.account.company = company
        create_chart.transition_create_account()

        receivable, = Account.search([
            ('kind', '=', 'receivable'),
            ('company', '=', company),
        ])
        payable, = Account.search([
            ('kind', '=', 'payable'),
            ('company', '=', company),
        ])
        create_chart.properties.company = company
        create_chart.properties.account_receivable = receivable
        create_chart.properties.account_payable = payable
        create_chart.transition_create_properties()

    def _get_account_by_kind(self, kind, company=None, silent=True):
        """Returns an account with given spec
        :param kind: receivable/payable/expense/revenue
        :param silent: dont raise error if account is not found
        """
        Account = POOL.get('account.account')
        Company = POOL.get('company.company')

        if company is None:
            company, = Company.search([], limit=1)

        accounts = Account.search([
            ('kind', '=', kind),
            ('company', '=', company)
        ], limit=1)
        if not accounts and not silent:
            raise Exception("Account not found")
        return accounts[0] if accounts else None

    def _create_fiscal_year(self, date=None, company=None):
        """
        Creates a fiscal year and requried sequences
        """
        FiscalYear = POOL.get('account.fiscalyear')
        Sequence = POOL.get('ir.sequence')
        SequenceStrict = POOL.get('ir.sequence.strict')
        Company = POOL.get('company.company')

        if date is None:
            date = datetime.date.today()

        if company is None:
            company, = Company.search([], limit=1)

        invoice_sequence, = SequenceStrict.create([{
            'name': '%s' % date.year,
            'code': 'account.invoice',
            'company': company,
        }])
        fiscal_year, = FiscalYear.create([{
            'name': '%s' % date.year,
            'start_date': date + relativedelta(month=1, day=1),
            'end_date': date + relativedelta(month=12, day=31),
            'company': company,
            'post_move_sequence': Sequence.create([{
                'name': '%s' % date.year,
                'code': 'account.move',
                'company': company,
            }])[0],
            'out_invoice_sequence': invoice_sequence,
            'in_invoice_sequence': invoice_sequence,
            'out_credit_note_sequence': invoice_sequence,
            'in_credit_note_sequence': invoice_sequence,
        }])
        FiscalYear.create_period([fiscal_year])
        return fiscal_year

    def login(self, client, username, password, assert_=True):
        """
        Tries to login.

        .. note::
            This method MUST be called within a context

        :param client: Instance of the test client
        :param username: The username, usually email
        :param password: The password to login
        :param assert_: Boolean value to indicate if the login has to be
                        ensured. If the login failed an assertion error would
                        be raised
        """
        rv = client.post(
            '/login', data={
                'email': username,
                'password': password,
            }
        )
        if assert_:
            self.assertEqual(rv.status_code, 302)
        return rv

    def setup_defaults(self):
        """
        Setting up default values.
        """

        usd, = self.Currency.create([{
            'name': 'US Dollar',
            'code': 'USD',
            'symbol': '$',
        }])

        # Create parties
        with Transaction().set_context(company=None):
            self.party, = self.Party.create([{
                'name': 'openlabs',
            }])

        self.company, = self.Company.create([{
            'party': self.party,
            'currency': usd,
        }])

        self.User.write(
            [self.User(USER)], {
                'main_company': self.company.id,
                'company': self.company.id,
            }
        )
        CONTEXT.update(self.User.get_preferences(context_only=True))

        # Create Fiscal Year
        self._create_fiscal_year(company=self.company.id)
        # Create Chart of Accounts
        self._create_coa_minimal(company=self.company.id)

        guest_party, = self.Party.create([{
            'name': 'Guest User',
        }])

        self.party2, = self.Party.create([{
            'name': 'Registered User',
        }])

        self.party3, = self.Party.create([{
            'name': 'Registered User 2',
        }])

        self.guest_user, = self.NereidUser.create([{
            'party': guest_party.id,
            'display_name': 'Guest User',
            'email': 'guest@openlabs.co.in',
            'password': 'password',
            'company': self.company.id,
        }])

        # Create test users
        self.registered_user, = self.NereidUser.create([{
            'party': self.party2.id,
            'display_name': 'Registered User',
            'email': 'email@example.com',
            'password': 'password',
            'company': self.company.id,
        }])
        self.registered_user2, = self.NereidUser.create([{
            'party': self.party3.id,
            'display_name': 'Registered User 2',
            'email': 'email2@example.com',
            'password': 'password2',
            'company': self.company.id,
        }])

        # create countries
        self._create_countries()
        self.available_countries = self.Country.search([], limit=5)

        en_us, = self.Language.search([('code', '=', 'en_US')])

        self.locale_en_us, = self.Locale.create([{
            'code': 'en_US',
            'language': en_us.id,
            'currency': usd.id,
        }])
        warehouse, = self.Location.search([
            ('type', '=', 'warehouse')
        ], limit=1)
        location, = self.Location.search([
            ('type', '=', 'storage')
        ], limit=1)

        payment_term, = self._create_payment_term()

        shop_price_list = self._create_pricelists()

        with Transaction().set_context(company=self.company.id):
            self.shop, = self.SaleShop.create([{
                'name': 'Default Shop',
                'price_list': shop_price_list,
                'warehouse': warehouse,
                'payment_term': payment_term,
                'company': self.company.id,
                'users': [('add', [USER])]
            }])

        self.User.set_preferences({'shop': self.shop})
        self.NereidWebsite.create([{
            'name': 'localhost',
            'company': self.company.id,
            'application_user': USER,
            'shop': self.shop,
            'default_locale': self.locale_en_us.id,
            'warehouse': warehouse,
            'stock_location': location,
            'countries': [('add', self.available_countries)],
            'guest_user': self.guest_user,
        }])

    def test_0010_create_wishlist(self):
        """
        Test to add a new wishlist.
        If wishlist already exist just return that wishlist.
        """

        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            self.setup_defaults()
            app = self.get_app()

            with app.test_client() as c:
                # Guest user tries to create wishlist
                rv = c.post(
                    '/wishlists',
                    data={
                        'name': 'Test',
                    }
                )
                self.assertEqual(rv.status_code, 302)
                # User login
                self.login(c, 'email@example.com', 'password')

                self.assertEqual(
                    len(current_user.wishlists), 0
                )
                rv = c.post(
                    '/wishlists',
                    data={
                        'name': 'Test',
                    }
                )
                self.assertEqual(
                    len(current_user.wishlists), 1
                )
                self.assertEqual(rv.status_code, 302)

                rv = c.post(
                    '/wishlists',
                    data={
                        'name': 'Test',
                    }
                )
                self.assertEqual(rv.status_code, 302)
                self.assertEqual(current_user.wishlists[0].name, 'Test')

                rv = c.post(
                    '/wishlists',
                    data={
                        'name': 'Test',
                    }, headers=[('X-Requested-With', 'XMLHttpRequest')]
                )
                self.assertEqual(rv.status_code, 200)

    def test_0020_view_list_of_wishlist(self):
        """
        Test to view all wishlist
        """

        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            self.setup_defaults()
            app = self.get_app()

            with app.test_client() as c:

                self.login(c, 'email@example.com', 'password')

                c.post(
                    '/wishlists',
                    data={
                        'name': 'Test',
                    }
                )
                c.post(
                    '/wishlists',
                    data={
                        'name': 'Test1',
                    }
                )
                rv = c.get('/wishlists')
                self.assertEqual(rv.status_code, 200)
                self.assertEqual(rv.data, '2')

    def test_0030_remove_wishlist(self):
        """
        Test to remove wishlist
        """

        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            self.setup_defaults()
            app = self.get_app()

            with app.test_client() as c:

                self.login(c, 'email@example.com', 'password')

                c.post(
                    '/wishlists',
                    data={
                        'name': 'Test',
                    }
                )
                c.post(
                    '/wishlists',

                    data={
                        'name': 'Test1',
                    }
                )
                self.assertEqual(
                    len(current_user.wishlists), 2
                )

                rv = c.delete(
                    '/wishlists/%d' % (current_user.wishlists[0].id, )
                )
                self.assertEqual(rv.status_code, 200)
                self.assertEqual(
                    len(current_user.wishlists), 1
                )

                rv = c.delete(
                    '/wishlists/%d' % (current_user.wishlists[0].id, ),
                    headers=[('X-Requested-With', 'XMLHttpRequest')]
                )
                self.assertEqual(rv.status_code, 200)
                self.assertEqual(
                    len(current_user.wishlists), 0
                )

    def test_0040_wishlist_products(self):
        """
        Test to add/remove a product to wishlist.
        """

        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            self.setup_defaults()
            app = self.get_app()

            uom, = self.Uom.search([], limit=1)
            values1 = {
                'name': 'Product-1',
                'type': 'goods',
                'list_price': Decimal('10'),
                'cost_price': Decimal('5'),
                'default_uom': uom.id,
                'products': [
                    ('create', [{
                        'uri': 'product-1',
                        'displayed_on_eshop': True
                    }])
                ]
            }
            values2 = {
                'name': 'Product-1',
                'type': 'goods',
                'list_price': Decimal('10'),
                'cost_price': Decimal('5'),
                'default_uom': uom.id,
                'products': [
                    ('create', [{
                        'uri': 'product-2',
                        'displayed_on_eshop': True
                    }])
                ]
            }

            template2, = self.Template.create([values2])
            template1, = self.Template.create([values1])

            with app.test_client() as c:
                self.login(c, 'email@example.com', 'password')

                # Add a product without creating any wishlist
                rv = c.post(
                    'wishlists/products',
                    data={
                        'product': template1.products[0].id,
                        'action': 'add',
                    }
                )
                self.assertEqual(rv.status_code, 302)
                self.assertEqual(len(current_user.wishlists), 1)
                self.assertEqual(len(current_user.wishlists[0].products), 1)
                # Add product to specific wishlist
                rv = c.post(
                    'wishlists/products',
                    data={
                        'product': template2.products[0].id,
                        'action': 'add',
                        'wishlist': current_user.wishlists[0].id,
                    }
                )
                self.assertEqual(rv.status_code, 302)
                self.assertEqual(
                    len(current_user.wishlists[0].products), 2
                )
                # Remove Product
                rv = c.post(
                    'wishlists/products',
                    data={
                        'product': template1.products[0].id,
                        'wishlist': current_user.wishlists[0].id,
                        'action': 'remove',
                    }
                )
                self.assertEqual(rv.status_code, 302)
                self.assertEqual(len(current_user.wishlists[0].products), 1)

                rv = c.post(
                    'wishlists/products',
                    data={
                        'product': 11,
                        'wishlist': current_user.wishlists[0].id,
                        'action': 'remove',
                    }
                )
                self.assertEqual(rv.status_code, 404)

                rv = c.post(
                    'wishlists/products',
                    data={
                        'product': 11,
                        'wishlist': current_user.wishlists[0].id,
                        'action': 'other',
                    }
                )
                self.assertEqual(rv.status_code, 404)

                # Test to see if no wishlist is found
                with self.assertRaises(ValueError):
                    c.post(
                        'wishlists/products',
                        data={
                            'product': template1.products[0].id,
                            'wishlist': 10,
                            'action': 'add',
                            }
                        )
                # xhr request
                rv = c.post(
                    'wishlists/products',
                    data={
                        'product': template2.products[0].id,
                        'action': 'remove',
                        'wishlist': current_user.wishlists[0].id,
                    }, headers=[('X-Requested-With', 'XMLHttpRequest')]

                )
                self.assertEqual(rv.status_code, 200)
                self.assertEqual(len(current_user.wishlists[0].products), 0)

                rv = c.post(
                    'wishlists/products',
                    data={
                        'product': template2.products[0].id,
                        'action': 'add',
                        'wishlist': current_user.wishlists[0].id,
                    }, headers=[('X-Requested-With', 'XMLHttpRequest')]

                )
                self.assertEqual(rv.status_code, 200)
                self.assertEqual(len(current_user.wishlists[0].products), 1)

    def test_0050_render_single_wishlist(self):
        """
        Test to render single wishlist.
        """

        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            self.setup_defaults()
            app = self.get_app()

            with app.test_client() as c:

                self.login(c, 'email@example.com', 'password')

                c.post(
                    '/wishlists',
                    data={
                        'name': 'Test',
                    }
                )
                self.assertEqual(len(current_user.wishlists), 1)

                rv = c.get(
                    '/wishlists/%d'
                    % (current_user.wishlists[0].id, )
                )
                self.assertEqual(rv.status_code, 200)
                self.assertEqual(rv.data, 'Test')

                # Xhr request
                rv = c.get(
                    '/wishlists/%d'
                    % (current_user.wishlists[0].id, ),
                    headers=[('X-Requested-With', 'XMLHttpRequest')]
                )

                self.assertEqual(rv.status_code, 200)

                # User trying to access wishlist of another user
                user1_wishlist_id = current_user.wishlists[0].id
                self.login(c, 'email2@example.com', 'password2')

                rv = c.get(
                    '/wishlists/%d' % (user1_wishlist_id, )
                )
                self.assertEqual(rv.status_code, 404)

    def test_0060_rename_wishlist(self):
        """
        Test rename a wishlist
        """

        Wishlist = POOL.get('wishlist.wishlist')

        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            self.setup_defaults()
            app = self.get_app()

            with app.test_client() as c:
                self.login(c, 'email@example.com', 'password')
                rv = c.post(
                    '/wishlists',
                    data={
                        'name': 'Test',
                    }
                )

                rv = c.post(
                    '/wishlists',
                    data={
                        'name': 'existing',
                    }
                )

                wishlist = current_user.wishlists[0]

                self.assertEqual(rv.status_code, 302)
                self.assertEqual(wishlist.name, 'Test')

                rv = c.post(
                    '/wishlists/%d'
                    % (wishlist.id, ),
                    data={
                        'name': 'existing',
                    }
                )
                self.assertEqual(rv.status_code, 302)
                self.assertEqual(wishlist.name, 'Test')
                rv = c.post(
                    '/wishlists/%d'
                    % (wishlist.id, ),
                    data={
                        'name': 'Test2',
                    }
                )

                self.assertEqual(rv.status_code, 302)
                wishlist = Wishlist(wishlist.id)    # reload the record
                self.assertEqual(wishlist.name, 'Test2')


def suite():
    "Nereid test suite"
    test_suite = unittest.TestSuite()
    test_suite.addTests(
        unittest.TestLoader().loadTestsFromTestCase(TestWishlist)
    )
    return test_suite


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
