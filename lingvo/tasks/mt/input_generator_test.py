# Lint as: python3
# Copyright 2018 The TensorFlow Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
"""Tests for input generator."""


import lingvo.compat as tf
from lingvo.core import py_utils
from lingvo.core import test_helper
from lingvo.core import test_utils
from lingvo.core import tokenizers
from lingvo.tasks.mt import input_generator
import numpy as np
from six.moves import range


class InputTest(test_utils.TestCase):

  def _CreateMlPerfInputParams(self):
    p = input_generator.MlPerfInput.Params()
    input_file = test_helper.test_src_dir_path(
        'tasks/mt/testdata/translate_ende_wmt32k-train-00511-of-00512')
    p.file_pattern = 'tfrecord:' + input_file
    p.file_random_seed = 31415
    p.file_parallelism = 1
    p.bucket_upper_bound = [20, 40]
    p.bucket_batch_limit = [4, 8]
    return p

  def _CreateMlPerfPackedInputParams(self):
    p = input_generator.MlPerfInput.Params()
    input_file = test_helper.test_src_dir_path(
        'tasks/mt/testdata/translate_ende_mlperf.packed.tfrecord')
    p.file_pattern = 'tfrecord:' + input_file
    p.packed_input = True
    p.file_random_seed = 31415
    p.file_parallelism = 1
    p.bucket_upper_bound = [20, 240]
    p.bucket_batch_limit = [4, 4]
    return p

  def _CreateNmtInputParams(self):
    p = input_generator.NmtInput.Params()
    input_file = test_helper.test_src_dir_path(
        'tasks/mt/testdata/wmt14_ende_wpm_32k_test.tfrecord')
    p.file_pattern = 'tfrecord:' + input_file
    p.file_random_seed = 31415
    p.file_parallelism = 1
    p.bucket_upper_bound = [20, 40]
    p.bucket_batch_limit = [4, 8]
    return p

  def testBasic(self):
    p = self._CreateNmtInputParams()
    with self.session(use_gpu=False):
      inp = input_generator.NmtInput(p)
      # Runs a few steps.
      for _ in range(10):
        self.evaluate(inp.GetPreprocessedInputBatch())

  def testMlPerfPackedInput(self):
    p = self._CreateMlPerfPackedInputParams()
    with self.session(use_gpu=False):
      inp = input_generator.MlPerfInput(p)
      for _ in range(1):
        fetched = py_utils.NestedMap(
            self.evaluate(inp.GetPreprocessedInputBatch()))
        tf.logging.info(fetched.src.ids.shape)
        tf.logging.info(fetched.src.segment_ids.shape)
        tf.logging.info(fetched.src.segment_pos.shape)
        tf.logging.info(fetched.tgt.segment_ids.shape)
        tf.logging.info(fetched.tgt.segment_pos.shape)

  def checkPadShape(self, x, pad, batch_size, actual_max, pad_length):
    # Check the shape: (batch, maxlen)
    self.assertEqual(x.shape, (batch_size, pad_length))
    # Check the padding.
    self.assertAllEqual(x[:, actual_max:],
                        np.full((batch_size, (pad_length - actual_max)), pad))

  def testMlPerfPackedInputPadToMax(self):
    p = self._CreateMlPerfPackedInputParams()
    p.source_max_length = 300
    p.target_max_length = 300
    p.pad_to_max_seq_length = True
    with self.session(use_gpu=False):
      inp = input_generator.MlPerfInput(p)
      for _ in range(1):
        fetched = py_utils.NestedMap(
            self.evaluate(inp.GetPreprocessedInputBatch()))

    self.checkPadShape(
        fetched.src.ids, pad=0, batch_size=4, actual_max=240, pad_length=300)

    self.checkPadShape(
        fetched.tgt.ids, pad=0, batch_size=4, actual_max=240, pad_length=300)

    self.checkPadShape(
        fetched.tgt.segment_ids,
        pad=0,
        batch_size=4,
        actual_max=240,
        pad_length=300)

    self.checkPadShape(
        fetched.tgt.segment_pos,
        pad=0,
        batch_size=4,
        actual_max=240,
        pad_length=300)

  def testMlPerf(self):
    p = self._CreateMlPerfInputParams()
    with self.session(use_gpu=False):
      inp = input_generator.MlPerfInput(p)
      # Runs a few steps.
      for _ in range(10):
        fetched = py_utils.NestedMap(
            self.evaluate(inp.GetPreprocessedInputBatch()))
        tf.logging.info(fetched)

  def testMlPerfPadToMax(self):
    p = self._CreateMlPerfInputParams()
    p.bucket_upper_bound = [20]
    p.bucket_batch_limit = [4]
    p.source_max_length = 30
    p.target_max_length = 30
    p.pad_to_max_seq_length = True

    with self.session(use_gpu=False):
      inp = input_generator.MlPerfInput(p)
      # Runs a few steps.
      for _ in range(10):
        fetched = py_utils.NestedMap(
            self.evaluate(inp.GetPreprocessedInputBatch()))

    def Check(x, pad):
      # Check the shape: (batch, maxlen)
      self.assertEqual(x.shape, (4, 30))
      # Check the padding.
      self.assertAllEqual(x[:, 20:], np.full((4, 10), pad))
    Check(fetched.src.ids, 0)
    Check(fetched.src.paddings, 1)
    Check(fetched.tgt.ids, 0)
    Check(fetched.tgt.labels, 0)
    Check(fetched.tgt.weights, 0)
    Check(fetched.tgt.paddings, 1)

  def testPadToMax(self):
    p = self._CreateNmtInputParams()
    p.bucket_upper_bound = [20]
    p.bucket_batch_limit = [4]
    p.source_max_length = 30
    p.target_max_length = 30
    p.pad_to_max_seq_length = True
    with self.session(use_gpu=False):
      inp = input_generator.NmtInput(p)
      fetched = py_utils.NestedMap(
          self.evaluate(inp.GetPreprocessedInputBatch()))

    def Check(x, pad):
      # Check the shape: (batch, maxlen)
      self.assertEqual(x.shape, (4, 30))
      # Check the padding.
      self.assertAllEqual(x[:, 20:], np.full((4, 10), pad))

    Check(fetched.src.ids, 0)
    Check(fetched.src.paddings, 1)
    Check(fetched.tgt.ids, 0)
    Check(fetched.tgt.labels, 0)
    Check(fetched.tgt.weights, 0)
    Check(fetched.tgt.paddings, 1)

  def testSplitSources(self):
    p = self._CreateNmtInputParams()
    num_splits = 2
    expected_ids_split_1 = [
        [
            228, 58, 854, 11, 392, 45, 77, 67, 1346, 30, 25, 10, 2283, 933, 14,
            3, 872, 4677, 5, 2
        ],
        [
            328, 22, 463, 571, 134, 10, 3815, 6311, 8, 2203, 3, 654, 2724, 1064,
            5, 2, 0, 0, 0, 0
        ],
    ]

    expected_ids_split_2 = [
        [
            16, 599, 11, 8, 113, 3, 145, 558, 489, 4373, 36, 55, 8988, 5, 2, 0,
            0, 0, 0, 0
        ],
        [
            16, 343, 95, 296, 4550, 4786, 1798, 23019, 8, 10296, 3, 107, 6428,
            1812, 5, 2, 0, 0, 0, 0
        ],
    ]

    with self.session(use_gpu=False):
      inp = input_generator.NmtInput(p)
      splits = inp.SplitInputBatch(num_splits)
      split_ids = self.evaluate([splits[0].src.ids, splits[1].src.ids])
      self.assertAllEqual(expected_ids_split_1, split_ids[0])
      self.assertAllEqual(expected_ids_split_2, split_ids[1])

  def testSplitTargets(self):
    p = self._CreateNmtInputParams()
    num_splits = 2

    with self.session(use_gpu=False):
      inp = input_generator.NmtInput(p)
      fetched = self.evaluate(inp.SplitInputBatch(num_splits))

    expected_ids_split_1 = [
        [
            1, 400, 5548, 12, 583, 43, 61, 179, 1265, 22, 27, 7193, 16, 5, 782,
            14077, 6734, 4, 0
        ],
        [
            1, 1639, 32, 1522, 93, 38, 6812, 2624, 9, 2440, 3, 39, 11, 2364,
            24238, 9, 317, 4, 0
        ],
    ]

    expected_ids_split_2 = [
        [
            1, 53, 17787, 12, 3, 5, 1554, 871, 9, 1398, 3, 2784, 18, 25579, 942,
            29828, 5998, 77, 4
        ],
        [
            1, 67, 4141, 11483, 2008, 6, 483, 46, 23, 14852, 3, 39, 5, 9732,
            495, 3176, 21523, 4, 0
        ],
    ]

    self.assertAllEqual(expected_ids_split_1, fetched[0].tgt.ids)
    self.assertAllEqual(expected_ids_split_2, fetched[1].tgt.ids)

  def testTextPackedInput(self):
    p = input_generator.TextPackedInput.Params()
    p.flush_every_n = 0
    p.require_sequential_order = True
    p.repeat_count = 1
    p.file_pattern = 'tfrecord:' + test_helper.test_src_dir_path(
        'tasks/mt/testdata/en_fr.tfrecord')
    p.pad_to_max_seq_length = True
    p.tokenizer = tokenizers.AsciiTokenizer.Params()
    p.input_file_type = 'sentence_proto'
    p.source_max_length = 22
    p.target_max_length = 24
    p.bucket_batch_limit = [2]
    with self.session() as sess:
      inp = p.Instantiate()
      batch_tensor = inp.GetPreprocessedInputBatch()
      for k, x in batch_tensor.FlattenItems():
        self.assertTrue(x.shape.is_fully_defined(), k)
      batch, num_examples = sess.run([batch_tensor, inp.GlobalBatchSize()])
    self.assertEqual(num_examples, 2)
    self.assertEqual(len(batch.src), 7)
    self.assertAllEqual(batch.src.strs,
                        [b'I love paragliding!', b'vol biv paragliding'])
    self.assertAllEqual(batch.tgt.strs,
                        [b"J'adore le parapente!", b'vol biv parapente'])
    self.assertAllEqual(
        batch.src.ids,
        np.array([
            [
                13, 3, 16, 19, 26, 9, 3, 20, 5, 22, 5, 11, 16, 13, 8, 13, 18,
                11, 35, 2, 2, 2
            ],
            [
                26, 19, 16, 3, 6, 13, 26, 3, 20, 5, 22, 5, 11, 16, 13, 8, 13,
                18, 11, 2, 2, 2
            ],
        ]))
    self.assertAllEqual(
        batch.tgt.ids,
        np.array([
            [
                1, 14, 32, 5, 8, 19, 22, 9, 3, 16, 9, 3, 20, 5, 22, 5, 20, 9,
                18, 24, 9, 35, 0, 0
            ],
            [
                1, 26, 19, 16, 3, 6, 13, 26, 3, 20, 5, 22, 5, 20, 9, 18, 24, 9,
                0, 0, 0, 0, 0, 0
            ],
        ]))
    self.assertAllEqual(
        batch.tgt.labels,
        np.array([
            [
                14, 32, 5, 8, 19, 22, 9, 3, 16, 9, 3, 20, 5, 22, 5, 20, 9, 18,
                24, 9, 35, 2, 2, 2
            ],
            [
                26, 19, 16, 3, 6, 13, 26, 3, 20, 5, 22, 5, 20, 9, 18, 24, 9, 2,
                2, 2, 2, 2, 2, 2
            ],
        ]))


if __name__ == '__main__':
  tf.test.main()
