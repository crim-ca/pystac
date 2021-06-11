from copy import deepcopy
from pystac.errors import STACTypeError
from typing import Any, Dict, Iterator, List, Optional, Collection, Iterable, Union

import pystac
from pystac.utils import make_absolute_href, is_absolute_href
from pystac.serialization.identify import identify_stac_object_type


ItemLike = Union[pystac.Item, Dict[str, Any]]


class ItemCollection(Collection[pystac.Item]):
    """Implementation of a GeoJSON FeatureCollection whose features are all STAC
    Items.

    All :class:`~pystac.Item` instances passed to the :class:`~ItemCollection` instance
    during instantiation are cloned and have their ``"root"`` URL cleared. Instances of
    this class implement the abstract methods of :class:`typing.Collection` and can also
    be added together (see below for examples using these methods).

    Any additional top-level fields in the FeatureCollection are retained in
    :attr:`~ItemCollection.extra_fields` by the :meth:`~ItemCollection.from_dict` and
    :meth:`~ItemCollection.from_file` methods and will be present in the serialized file
    from :meth:`~ItemCollection.save_object`.

    Arguments:

        items : List of :class:`~pystac.Item` instances to include in the
            :class:`~ItemCollection`.
        extra_fields : Dictionary of additional top-level fields included in the
            :class:`~ItemCollection`.
        clone_items : Optional flag indicating whether :class:`~pystac.Item` instances
            should be cloned before storing in the :class:`~ItemCollection`. Setting to
            ``False`` will result in faster instantiation, but any changes made to
            :class:`~pystac.Item` instances in the :class:`~ItemCollection` will also
            mutate the original :class:`~pystac.Item`. Defaults to ``True``.

    Examples:

        Loop over all items in the :class`~ItemCollection`

        >>> item_collection: ItemCollection = ...
        >>> for item in item_collection:
        ...     ...

        Get the number of :class:`~pytac.Item` instances in the
        :class:`~ItemCollection`

        >>> length: int = len(item_collection)

        Check if an :class:`~pystac.Item` is in the :class:`~ItemCollection`. Note
        that you must use `clone_items=False` for this to return ``True``, since
        equality of PySTAC objects is currently evaluated using default object
        equality (i.e. ``item_1 is item_2``).

        >>> item: Item = ...
        >>> item_collection = ItemCollection(items=[item], clone_items=False)
        >>> assert item in item_collection

        Combine :class:`~ItemCollection` instances

        >>> item_1: Item = ...
        >>> item_2: Item = ...
        >>> item_3: Item = ...
        >>> item_collection_1 = ItemCollection(
        ...     items=[item_1, item_2],
        ...     clone_items=False
        ... )
        >>> item_collection_2 = ItemCollection(
        ...     items=[item_2, item_3],
        ...     clone_items=False
        ... )
        >>> combined = item_collection_1 + item_collection_2
        >>> assert len(combined) == 3
        # If an item is present in both ItemCollections it will only be added once
    """

    items: List[pystac.Item]
    """List of :class:`pystac.Item` instances contained in this ``ItemCollection``."""

    extra_fields: Dict[str, Any]
    """Dictionary of additional top-level fields for the GeoJSON
    FeatureCollection."""

    def __init__(
        self,
        items: Iterable[ItemLike],
        extra_fields: Optional[Dict[str, Any]] = None,
        clone_items: bool = True,
    ):
        def map_item(item_or_dict: ItemLike) -> pystac.Item:
            # Converts dicts to pystac.Items and clones if necessary
            if isinstance(item_or_dict, pystac.Item):
                return item_or_dict.clone() if clone_items else item_or_dict
            else:
                return pystac.Item.from_dict(item_or_dict)

        self.items = list(map(map_item, items))
        self.extra_fields = extra_fields or {}

    def __getitem__(self, idx: int) -> pystac.Item:
        return self.items[idx]

    def __iter__(self) -> Iterator[pystac.Item]:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __contains__(self, __x: object) -> bool:
        return __x in self.items

    def __add__(self, other: object) -> "ItemCollection":
        if not isinstance(other, ItemCollection):
            return NotImplemented

        combined = []
        for item in self.items + other.items:
            if item not in combined:
                combined.append(item)

        return ItemCollection(items=combined, clone_items=False)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes an :class:`ItemCollection` instance to a JSON-like dictionary."""
        return {
            "type": "FeatureCollection",
            "features": [item.to_dict() for item in self.items],
            **self.extra_fields,
        }

    def clone(self) -> "ItemCollection":
        """Creates a clone of this instance. This clone is a deep copy; all
        :class:`~pystac.Item` instances are cloned and all additional top-level fields
        are deep copied."""
        return self.__class__(
            items=[item.clone() for item in self.items],
            extra_fields=deepcopy(self.extra_fields),
        )

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ItemCollection":
        """Creates a :class:`ItemCollection` instance from a dictionary.

        Arguments:
            d : The dictionary from which the :class:`~ItemCollection` will be created
        """
        if identify_stac_object_type(d) != pystac.STACObjectType.ITEMCOLLECTION:
            raise STACTypeError("Dict is not a valid ItemCollection")

        items = [pystac.Item.from_dict(item) for item in d.get("features", [])]
        extra_fields = {k: v for k, v in d.items() if k not in ("features", "type")}

        # Since we are reading these Items from a dict within this method, there will be
        # no other references and we do not need to clone them.
        return cls(items=items, extra_fields=extra_fields, clone_items=False)

    @classmethod
    def from_file(
        cls, href: str, stac_io: Optional[pystac.StacIO] = None
    ) -> "ItemCollection":
        """Reads a :class:`ItemCollection` from a JSON file.

        Arguments:
            href : Path to the file.
            stac_io : A :class:`~pystac.StacIO` instance to use for file I/O
        """
        if stac_io is None:
            stac_io = pystac.StacIO.default()

        if not is_absolute_href(href):
            href = make_absolute_href(href)

        d = stac_io.read_json(href)

        return cls.from_dict(d)

    def save_object(
        self,
        dest_href: str,
        stac_io: Optional[pystac.StacIO] = None,
    ) -> None:
        """Saves this instance to the ``dest_href`` location.

        Args:
            dest_href : Location to which the file will be saved.
            stac_io: Optional :class:`~pystac.StacIO` instance to use. If not provided,
                will use the default instance.
        """
        if stac_io is None:
            stac_io = pystac.StacIO.default()

        stac_io.save_json(dest_href, self.to_dict())
