# blender-addons-commons
# Copyright (C) 2021 coldrye solutions, Carsten Klein and Contributors
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from enum import IntEnum
import re
from typing import Literal, Union
from dataclasses import dataclass

__all__ = [
    'ReleaseState',
    'Version'
]

# Addon Versioning Schemas
# Blender Version
# <release>.<feature>.<patch>.<state>.<increment>.<blender-release>.<blender-feature>.<blender-patch>[.<build>]
# Semver Variant
# <major>.<minor>.<patch>-<state.name>[<increment>]-<blender-release>.<blender-feature>.<blender-patch>[+<build>]

_VERSION_PART_REGEXP = r'(?P<r>\d+)[.](?P<f>\d+)[.](?P<p>\d+)'
_VERSION_STATE_PART_REGEXP = r'[.](?P<s>\d)[.](?P<i>\d+)'
_VERSION_BLENDER_VERSION_PART_REGEXP = r'(?P<br>\d+)[.](?P<bf>\d+)[.](?P<bp>\d+)'
_VERSION_BLENDER_PART_REGEXP = r'[.]' + _VERSION_BLENDER_VERSION_PART_REGEXP
_VERSION_BUILD_PART_REGEXP = r'([.](?P<b>\d+))?'

_VERSION_REGEXP = ''.join([
    r'^', _VERSION_PART_REGEXP, _VERSION_STATE_PART_REGEXP, _VERSION_BLENDER_PART_REGEXP,
    _VERSION_BUILD_PART_REGEXP, r'$'
])

_SEMVER_PRERELEASE_PART_REGEXP = r'[-](?P<s>[a-zA-Z]+)(?P<i>\d+)?[-]' + _VERSION_BLENDER_VERSION_PART_REGEXP
_SEMVER_BUILD_PART_REGEXP = r'([+](?P<b>\d+))?'

_SEMVER_REGEXP = ''.join([
    r'^',
    _VERSION_PART_REGEXP,
    _SEMVER_PRERELEASE_PART_REGEXP,
    _SEMVER_BUILD_PART_REGEXP,
    r'$'
])


class ReleaseState(IntEnum):
    """Representation of a release state."""
    ALPHA = 1
    BETA = 2
    RC = 3
    STABLE = 4

    @classmethod
    def bump(cls, state: 'ReleaseState') -> 'ReleaseState':
        """Bumps the specified state by one. A stable release state cannot be bumped and remains stable.

        >>> ReleaseState.bump(ReleaseState.ALPHA)
        <ReleaseState.BETA: 2>
        >>> ReleaseState.bump(ReleaseState.BETA)
        <ReleaseState.RC: 3>
        >>> ReleaseState.bump(ReleaseState.RC)
        <ReleaseState.STABLE: 4>
        >>> ReleaseState.bump(ReleaseState.STABLE)
        <ReleaseState.STABLE: 4>
        """
        if state == 4:
            return state
        else:
            return ReleaseState(state + 1)

    @classmethod
    def from_value(cls, value: Union[int, str]) -> 'ReleaseState':
        """Returns a valid release state from either string or int.

        >>> ReleaseState.from_value(1)
        <ReleaseState.ALPHA: 1>
        >>> ReleaseState.from_value('BETA')
        <ReleaseState.BETA: 2>
        >>> ReleaseState.from_value(0)
        Traceback (most recent call last):
        ValueError: 0 is not a valid ReleaseState
        """
        if type(value) == str and value in ('ALPHA', 'BETA', 'RC', 'STABLE'):
            return ReleaseState[value]
        return ReleaseState(int(value))


@dataclass(order=True, frozen=True)
class Version:
    release: int
    feature: int
    patch: int
    state: Literal[ReleaseState.ALPHA, ReleaseState.BETA, ReleaseState.RC, ReleaseState.STABLE]
    increment: int
    brelease: int
    bfeature: int
    bpatch: int
    build: int

    def __str__(self) -> str:
        """Returns a string representation that can be used with the version meta data file

        :return: the addon version string

        >>> str(Version(release=1, feature=0, patch=0, state=ReleaseState.ALPHA, increment=1, brelease=2, bfeature=93, bpatch=0, build=0))
        '1.0.0.1.1.2.93.0.0'
        """
        return '.'.join([str(item) for item in Version.to_tuple(self)])

    @classmethod
    def from_string(cls, version: str) -> 'Version':
        """Returns a version from either a valid addon version string or a valid addon semver version string.

        :param version: the addon version string
        :return: a version instance

        >>> Version.from_string('1.0.0.1.1.2.93.0.0')
        Version(release=1, feature=0, patch=0, state=<ReleaseState.ALPHA: 1>, increment=1, brelease=2, bfeature=93, bpatch=0, build=0)
        >>> Version.from_string('1.0.0-ALPHA1-2.93.0')
        Version(release=1, feature=0, patch=0, state=<ReleaseState.ALPHA: 1>, increment=1, brelease=2, bfeature=93, bpatch=0, build=0)
        >>> Version.from_string('1.0.0-ALPHA1')
        Traceback (most recent call last):
        ValueError: "1.0.0-ALPHA1" is not a valid addon version string, e.g. "1.0.0.1.1.2.93.0.0" or "1.0.0-ALPHA1-2.93.0"
        >>> Version.from_string('1.0.0-ALPHA1-0.0.0')
        Traceback (most recent call last):
        ValueError: no blender min version requirement specified
        >>> Version.from_string('1.0.0.1.1')
        Traceback (most recent call last):
        ValueError: "1.0.0.1.1" is not a valid addon version string, e.g. "1.0.0.1.1.2.93.0.0" or "1.0.0-ALPHA1-2.93.0"
        >>> Version.from_string('1.0.0.1.1.0.0.0')
        Traceback (most recent call last):
        ValueError: no blender min version requirement specified
        """
        matches = re.match(_VERSION_REGEXP, version)
        if matches is None:
            ex_handled = None
            try:
                return Version._from_semver_string(version)
            except ValueError as ex:
                if 'blender' in str(ex):
                    raise ex
                ex_handled = ex
            finally:
                if ex_handled:
                    raise ValueError(
                        '"%s" is not a valid addon version string, e.g. "1.0.0.1.1.2.93.0.0" or "1.0.0-ALPHA1-2.93.0"'
                        % version
                    ) from ex_handled

        result = Version._from_dict(matches.groupdict())
        Version._validate_blender(result)
        return result

    @classmethod
    def _from_semver_string(cls, version: str) -> 'Version':
        """Returns a version from a valid addon semver version string.

        :param version: the addon semver version string
        :return: a version instance

        >>> Version._from_semver_string('1.0.0-ALPHA1-2.93.0')
        Version(release=1, feature=0, patch=0, state=<ReleaseState.ALPHA: 1>, increment=1, brelease=2, bfeature=93, bpatch=0, build=0)
        >>> Version._from_semver_string('1.0.0-ALPHA1-2.93.0+234')
        Version(release=1, feature=0, patch=0, state=<ReleaseState.ALPHA: 1>, increment=1, brelease=2, bfeature=93, bpatch=0, build=234)
        >>> Version._from_semver_string('1.0.0-ALPHA1-0.0.0')
        Traceback (most recent call last):
        ValueError: no blender min version requirement specified
        >>> Version._from_semver_string('1.0.0-ALPHA1')
        Traceback (most recent call last):
        ValueError: "1.0.0-ALPHA1" is not a valid addon semver version string, e.g. "1.0.0-ALPHA1-2.93.0"
        """
        matches = re.match(_SEMVER_REGEXP, version)
        if matches is None:
            raise ValueError(
                '"%s" is not a valid addon semver version string, e.g. "1.0.0-ALPHA1-2.93.0"' % version
            )
        result = Version._from_dict(matches.groupdict())
        Version._validate_blender(result)
        return result

    @classmethod
    def _from_dict(cls, d: dict) -> 'Version':
        return Version.from_tuple((
            int(d['r']),
            int(d['f']),
            int(d['p']),
            ReleaseState.from_value(d['s']),
            int(d['i']) if d['i'] else 0,
            int(d['br']),
            int(d['bf']),
            int(d['bp']),
            int(d['b']) if d['b'] else 0
        ))

    @classmethod
    def from_tuple(cls, version: tuple) -> 'Version':
        """Returns a version from a tuple one might get from bl_info."""
        return Version(*version)

    @classmethod
    def to_tuple(cls, version: 'Version') -> tuple:
        """Returns a tuple representation of the version that can be used with bl_info."""
        return (version.release, version.feature, version.patch, version.state.value, version.increment,
                version.brelease, version.bfeature, version.bpatch, version.build)

    @classmethod
    def to_semver(cls, version: 'Version') -> str:
        """Returns a semver representation of the version.

        :param version: the version
        :return: the addon semver version string
        """
        return ''.join([
            '%d.%d.%d' % (version.release, version.feature, version.patch),
            '-%s%s-%d.%d.%d' % (
                version.state.name,
                '' if version.state == ReleaseState.STABLE else str(version.increment),
                version.brelease,
                version.bfeature,
                version.bpatch
            ),
            '+%d' % version.build if version.build else ''
        ])

    @classmethod
    def bump(cls, version, release: bool = False, feature: bool = False, patch: bool = False,
             state: bool = False, increment: bool = False, build: int = None, blender: tuple = None) -> 'Version':
        """Bumps the version to a new version.

        :param version: the version to bump
        :param release: True whether to increment the release number
        :param feature: True whether to increment the feature number
        :param patch: True whether to increment the patch number
        :param state: True whether to increment the release state
        :param increment: True whether to increment the release state increment
        :param build: the build number will be set to the value
        :param blender: the blender min version requirement will be set to the value
        :return: the bumped version
        """

        tmp = list(Version.to_tuple(version))

        # fix state as it is now an int
        tmp[3] = ReleaseState.from_value(tmp[3])

        if release or feature or patch:
            if release:
                tmp[0] = version.release + 1
                tmp[1] = 0  # feature
            elif feature:
                tmp[1] = version.feature + 1
            elif patch:
                tmp[2] = version.patch + 1

            if release or feature:
                tmp[2] = 0  # patch
                tmp[3] = ReleaseState.ALPHA
                tmp[4] = 1  # increment
        elif state:
            tmp[3] = ReleaseState.bump(version.state)
            tmp[4] = 0 if state == ReleaseState.STABLE else 1
        elif increment and tmp[3] != ReleaseState.STABLE:
            tmp[4] = version.increment + 1

        if release or feature or patch or state or increment:
            # we do not have a build yet
            tmp[8] = 0  # build

        if build:
            tmp[8] = build

        if blender:
            tmp[5] = blender[0]  # brelease
            tmp[6] = blender[1]  # bfeature
            tmp[7] = blender[2]  # bpatch

        result = Version.from_tuple(tuple(tmp))
        Version._validate_blender(result)
        return result

    @classmethod
    def _validate_blender(cls, version: 'Version') -> None:
        """Validates the blender min version requirement.

        :param version: the version
        """
        if not version.brelease:
            raise ValueError('no blender min version requirement specified')

    # TODO: possibly unused
    def is_stable(self) -> bool:
        return self.state == ReleaseState.STABLE

    # TODO: possibly unused
    def is_alpha(self) -> bool:
        return self.state == ReleaseState.ALPHA

    # TODO: possibly unused
    def is_beta(self) -> bool:
        return self.state == ReleaseState.BETA

    # TODO: possibly unused
    def is_rc(self) -> bool:
        return self.state == ReleaseState.RC
