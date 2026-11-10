from src.utils.reports import change_class, price_change_classes


class TestChangeClass:
    def test_sign_picks_the_class(self):
        assert [change_class(v) for v in (2.5, -0.1, 0)] == ['up', 'down', 'flat']


class TestPriceChangeClasses:
    """Rows arrive newest first, so each close is compared with the row after it."""

    @staticmethod
    def closes(*values):
        return [{'close_price': v} for v in values]

    def test_compares_each_day_with_the_one_before(self):
        assert price_change_classes(self.closes(12, 10, 11, 11)) == ['up', 'down', 'flat', 'flat']

    def test_the_oldest_row_has_nothing_to_compare_with(self):
        assert price_change_classes(self.closes(10)) == ['flat']

    def test_a_missing_close_is_flat_on_both_sides(self):
        assert price_change_classes(self.closes(12, None, 10)) == ['flat', 'flat', 'flat']
