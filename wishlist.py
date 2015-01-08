# -*- coding: utf-8 -*-
"""
    nereid_wishlist.py

    :copyright: (c) 2014 by Openlabs Technologies & Consulting (P) Limited
    :license: BSD, see LICENSE for more details.
"""

from trytond.pool import PoolMeta, Pool
from trytond.model import ModelView, ModelSQL, fields
from nereid import login_required, current_user, request, \
    redirect, url_for, render_template, route, abort, flash
from wtforms import ValidationError

__all__ = [
    'NereidUser', 'Wishlist', 'Product',
    'ProductWishlistRelationship',
    ]
__metaclass__ = PoolMeta


class Product:
    """
    Extension of product variant
    """
    __name__ = 'product.product'

    wishlists = fields.Many2Many(
        'product.wishlist-product',
        'product', 'wishlist', 'Wishlists'
    )


class NereidUser:
    """
    Extension of Nereid User
    """
    __name__ = 'nereid.user'

    wishlists = fields.One2Many(
        'wishlist.wishlist', 'nereid_user', 'Wishlist'
    )


class Wishlist(ModelSQL, ModelView):
    """
    Wishlist
    """
    __name__ = "wishlist.wishlist"

    nereid_user = fields.Many2One(
        'nereid.user', 'Nereid User', select=True, required=True
    )
    name = fields.Char('Name', required=True, select=True)
    products = fields.Many2Many(
        'product.wishlist-product',
        'wishlist', 'product', 'Products',
    )

    @classmethod
    def _search_or_create_wishlist(cls, name="Default"):
        """
        Search wishlist according to name.
        if wishlist exist return wishlist, if not create a
        new wishlist named Default and return that wishlist

        return type: wishlist
        """
        try:
            wishlist, = cls.search([
                ('nereid_user', '=', current_user.id),
                ('name', '=', name),
            ])
        except ValueError:
            wishlist, = cls.create([{
                'name': name,
                'nereid_user': current_user.id,
            }])
        return wishlist

    @classmethod
    @route('/wishlists', methods=["GET", "POST"])
    @login_required
    def render_wishlists(cls):
        """
        Render all wishlist of the current user.
        if request is post and name is passed then call method
        _search_or_create_wishlist.
        """
        if request.method == 'POST' and request.form.get("name"):
            wishlist = cls._search_or_create_wishlist(request.form.get("name"))
            if request.is_xhr:
                # TODO: send all wishlist as serialized data
                return 'success', 200
            return redirect(
                url_for(
                    'wishlist.wishlist.render_wishlist', active_id=wishlist.id
                )
            )
        return render_template('wishlists.jinja')

    @route(
        '/wishlists/<int:active_id>',
        methods=["POST", "GET", "DELETE"]
    )
    @login_required
    def render_wishlist(self):
        """
        Render specific wishlist of current user.
        rename wishlist on post  and delete on delete request
        """
        Wishlist = Pool().get('wishlist.wishlist')

        if self.nereid_user != current_user:
            abort(404)

        if request.method == "POST" and request.form.get('name'):

            name = request.form.get('name')
            wishlist = Wishlist.search([
                ('nereid_user', '=', current_user.id),
                ('name', '=', name),
            ], limit=1)
            if wishlist:
                flash('Wishlist with name: ' + name + ' already exists.')
                return redirect(request.referrer)

            else:
                self.write([self], {'name': name})
                flash('Changed name of wishlist to ' + name + '.')
            if request.is_xhr:
                return 'success', 200

            return redirect(request.referrer)

        elif request.method == "DELETE":
            Wishlist.delete([self])
            if request.is_xhr:
                # TODO: send serialized data of current wishlist
                return 'success', 200

            return url_for('wishlist.wishlist.render_wishlists')

        return render_template('wishlist.jinja', wishlist=self)

    @classmethod
    @route('/wishlists/products', methods=["POST"])
    @login_required
    def wishlist_product(cls):
        """
        Add/Remove product in wishlist.
        If wishlist_id is passed then search for wishlist and add/remove
        product else create a default wishlist and add product.

        :params
            wishlist: Get the id of wishlist
            product: Get product id
            action: add or remove, add will add product to wishlist.
                remove will unlink product from wishlist
        """
        Product = Pool().get('product.product')

        wishlist_id = request.form.get("wishlist", type=int)
        if wishlist_id:
            try:
                wishlist, = cls.search([
                    ('id', '=', wishlist_id),
                    ('nereid_user', '=', current_user.id),
                ])
            except ValueError:
                raise ValidationError("Wishlist not valid!")
        else:
            wishlist = cls._search_or_create_wishlist()
        product = Product.search([
            ('id', '=', request.form.get("product", type=int)),
            ('displayed_on_eshop', '=', True),
            ('template.active', '=', True),
        ], limit=1)
        if not product or request.form.get('action') not in ['add', 'remove']:
            abort(404)
        cls.write([wishlist], {
            'products': [(request.form.get('action'), product)],
        })
        if request.is_xhr:
            # TODO: Send serailized data of wishllist
            return 'success', 200

        return redirect(
            url_for(
                'wishlist.wishlist.render_wishlist',
                active_id=wishlist.id
            )
        )


class ProductWishlistRelationship(ModelSQL):
    """
    This is the relation between wishlist and a product.
    """
    __name__ = 'product.wishlist-product'

    product = fields.Many2One(
        'product.product', 'Product',
        domain=[
            ('displayed_on_eshop', '=', True),
            ('template.active', '=', True),
        ],
        ondelete='CASCADE', select=True, required=True,
    )
    wishlist = fields.Many2One(
        'wishlist.wishlist', 'Wishlist',
        ondelete='CASCADE', select=True, required=True
    )
