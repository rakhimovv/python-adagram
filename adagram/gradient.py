from __future__ import print_function, division
import random
import time

import numpy as np

from adagram.stick_breaking import expected_logpi as var_init_z
from adagram.learn import var_update_z, inplace_update


def inplace_train(vm, dictionary, train_filename, window_length,
        batch_size=64000, start_lr=0.025, context_cut=True, epochs=1,
        sense_threshold=1e-32):
    # FIXME - epochs
    total_words = float(dictionary.frequencies.sum())
    total_ll = [0.0, 0.0]
    vm.counts[0,:] = vm.frequencies
    for words_read, doc in _words_reader(
            dictionary, train_filename, batch_size):
        print('{:>8.2%}'.format(words_read / total_words))
        _inplace_train(
            vm, doc, window_length, start_lr, total_words, words_read, total_ll,
            context_cut=context_cut, sense_threshold=sense_threshold)


def _inplace_train(vm, doc, window_length, start_lr, total_words, words_read,
        total_ll, context_cut, sense_threshold, report_batch_size=10000):
    in_grad = np.zeros((vm.dim, vm.prototypes), dtype=np.float32)
    out_grad = np.zeros(vm.dim, dtype=np.float32)
    z = np.zeros(vm.prototypes, dtype=np.float64)
    senses = 0.
    max_senses = 0.
    min_lr = start_lr * 1e-4
    t0 = time.time()
    for i, w in enumerate(doc):
        lr = max(start_lr * (1 - words_read / (total_words + 1)), min_lr)
        window = window_length
        if context_cut:
            window -= random.randint(1, window_length - 1)

        z[:] = 0.

        n_senses = var_init_z(vm, z, w)
        senses += n_senses
        max_senses = max(max_senses, n_senses)
        context = [doc[j] for j in xrange(
            max(0, i - window), min(len(doc), i + window + 1)) if i != j]
        for _w in context:
            var_update_z(vm, w, _w, z)
        np.subtract(z, z.max(), out=z)
        np.exp(z, out=z)
        np.divide(z, z.sum(), out=z)

        for _w in context:
            ll = inplace_update(
                vm, w, _w, z, lr, in_grad, out_grad, sense_threshold)
            total_ll[0] += ll
        total_ll[1] += len(context)
        words_read += 1

        #variational update for q(pi_v)
        _var_update_counts(vm, w, z, lr)

        if i and i % report_batch_size == 0:
            t1 = time.time()
            print('{:.2%} {:.4f} {:.4f} {:.1f}/{:.1f} {:.2f} kwords/sec'\
                .format(words_read / total_words, total_ll[0] / total_ll[1],
                        lr, senses / i, max_senses,
                        report_batch_size / 1000 / (t1 - t0)))
            t0 = t1


def _var_update_counts(vm, w, z, lr):
    counts = vm.counts[:, w]
    freq = vm.frequencies[w]
    for k in xrange(vm.prototypes):
        counts[k] += lr * (z[k] * freq - counts[k])


def _words_reader(dictionary, train_filename, batch_size):
    idx = 0
    words_read = 0
    doc = np.zeros(batch_size, dtype=np.int32)
    with open(train_filename, 'rb') as f:
        for line in f:
            line = line.decode('utf-8').strip()
            for w in line.split():
                try: w_id = dictionary.word2id[w]
                except KeyError: continue
                doc[idx] = w_id
                idx += 1
                if idx == batch_size:
                    yield words_read, doc
                    words_read += idx
                    idx = 0
        yield words_read, doc[:idx]

