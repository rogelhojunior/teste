from custom_auth.models import Corban


def get_subordinate_ids_at_all_levels(corban):
    subordinate_ids = set(
        Corban.objects.filter(parent_corban=corban).values_list('id', flat=True)
    )

    for sub_id in list(subordinate_ids):
        subordinate_ids.update(
            get_subordinate_ids_at_all_levels(Corban.objects.get(id=sub_id))
        )

    return subordinate_ids
