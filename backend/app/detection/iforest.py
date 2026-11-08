"""IsolationForest mandiri (tanpa dependensi eksternal) — ELANG-1 (PRD FR-103).

Implementasi ringkas algoritma Isolation Forest (Liu et al., 2008) memakai pustaka
standar saja, agar selaras dengan prinsip air-gapped (tanpa pip eksternal saat
runtime) dan portabel lintas Python 3.12/3.14.

Skor anomali s(x) = 2^(-E(h(x)) / c(psi)), 0..1; makin tinggi makin anomali.
Anomali terisolasi lebih cepat (jalur lebih pendek) sehingga skornya tinggi.
"""
from __future__ import annotations

import math
import random
from typing import Sequence

_EULER = 0.5772156649015329

Vector = Sequence[float]


def _c_factor(n: int) -> float:
    """Rata-rata panjang jalur BST tak berhasil untuk n titik (koreksi normalisasi)."""
    if n <= 1:
        return 0.0
    return 2.0 * (math.log(n - 1) + _EULER) - 2.0 * (n - 1) / n


# Node internal: ("int", feature, split, left, right); eksternal: ("ext", size)
_Node = tuple


def _build(rows: list[Vector], depth: int, max_depth: int, rng: random.Random, n_feat: int) -> _Node:
    if depth >= max_depth or len(rows) <= 1:
        return ("ext", len(rows))
    f = rng.randrange(n_feat)
    vals = [r[f] for r in rows]
    lo, hi = min(vals), max(vals)
    if lo == hi:
        return ("ext", len(rows))
    split = rng.uniform(lo, hi)
    left = [r for r in rows if r[f] < split]
    right = [r for r in rows if r[f] >= split]
    return ("int", f, split, _build(left, depth + 1, max_depth, rng, n_feat),
            _build(right, depth + 1, max_depth, rng, n_feat))


def _path_length(x: Vector, node: _Node, depth: int) -> float:
    if node[0] == "ext":
        return depth + _c_factor(node[1])
    _, f, split, left, right = node
    return _path_length(x, left, depth + 1) if x[f] < split else _path_length(x, right, depth + 1)


class IsolationForest:
    def __init__(self, n_trees: int = 100, sample_size: int = 256, seed: int = 1337) -> None:
        self.n_trees = n_trees
        self.sample_size = sample_size
        self.seed = seed
        self._trees: list[_Node] = []
        self._psi = 0
        self._n_feat = 0

    def fit(self, X: list[Vector]) -> "IsolationForest":
        if not X:
            raise ValueError("IsolationForest.fit: data kosong")
        rng = random.Random(self.seed)
        n = len(X)
        self._psi = min(self.sample_size, n)
        self._n_feat = len(X[0])
        max_depth = max(1, math.ceil(math.log2(max(2, self._psi))))
        self._trees = []
        for _ in range(self.n_trees):
            sample = X if n <= self._psi else rng.sample(X, self._psi)
            self._trees.append(_build(list(sample), 0, max_depth, rng, self._n_feat))
        return self

    def score(self, x: Vector) -> float:
        if not self._trees:
            raise RuntimeError("Model belum di-fit")
        avg = sum(_path_length(x, t, 0) for t in self._trees) / len(self._trees)
        c = _c_factor(self._psi) or 1.0
        return 2.0 ** (-avg / c)

    def score_all(self, X: list[Vector]) -> list[float]:
        return [self.score(x) for x in X]
