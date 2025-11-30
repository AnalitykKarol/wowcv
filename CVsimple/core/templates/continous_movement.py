"""
Continuous Movement - Compatibility Wrapper
Zachowuje 100% kompatybilność z istniejącym kodem
Automatycznie przekierowuje do nowej modularnej implementacji
"""

# Import nowej implementacji z combat_systems
from CVsimple.core.templates.combat_systems import ContinuousMovement

# Re-export dla zachowania kompatybilności
__all__ = ['ContinuousMovement']

# Użytkownik może nadal importować tak jak wcześniej:
# from continuous_movement import ContinuousMovement
#
# Wszystko będzie działać identycznie!