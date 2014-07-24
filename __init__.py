# -*- coding: utf-8 -*-
"""
    __init__.py

    :copyright: (c) 2014 by Openlabs Technologies & Consulting (P) Limited
    :license: BSD, see LICENSE for more details.
"""
from trytond.pool import Pool
from wishlist import NereidUser, Wishlist, Product, \
    ProductWishlistRelationship


def register():
    Pool.register(
        NereidUser,
        Wishlist,
        Product,
        ProductWishlistRelationship,
        module='nereid_wishlist', type_='model'
    )
