# -*- coding: utf-8 -*-
'''

    nereid_wishlist test suite

    :copyright: (c) 2014 by Openlabs Technologies & Consulting (P) Ltd.
    :license: GPLv3, see LICENSE for more details
'''
import unittest
from decimal import Decimal

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

        self.templates = {
            'wishlists.jinja':
                '{{ current_user.wishlists| length }}',
            'wishlist.jinja':
                '{{ wishlist.name }}',
        }

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
        self.party, = self.Party.create([{
            'name': 'openlabs',
        }])

        self.party2, = self.Party.create([{
            'name': 'Registered User',
        }])

        self.party3, = self.Party.create([{
            'name': 'Registered User 2',
        }])

        self.company, = self.Company.create([{
            'party': self.party,
            'currency': usd,
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
        self.NereidWebsite.create([{
            'name': 'localhost',
            'company': self.company.id,
            'application_user': USER,
            'default_locale': self.locale_en_us.id,
            'warehouse': warehouse,
            'stock_location': location,
            'countries': [('add', self.available_countries)],
        }])

    def test_0010_create_wishlist(self):
        """
        Test to add a new wishlist.
        If wishlist already exist just return that wishlist.
        """

        with Transaction().start(DB_NAME, USER, CONTEXT):
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

        with Transaction().start(DB_NAME, USER, CONTEXT):
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

        with Transaction().start(DB_NAME, USER, CONTEXT):
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

        with Transaction().start(DB_NAME, USER, CONTEXT):
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

        with Transaction().start(DB_NAME, USER, CONTEXT):
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

        with Transaction().start(DB_NAME, USER, CONTEXT):
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
