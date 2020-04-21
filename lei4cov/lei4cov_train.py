import tensorflow as tf
import numpy as np
import pickle
import os
from lit2vec import Lei4Cov
from hparams import Hparams


def load_data(x_file, n_split):
    seqs = list()
    for i in range(n_split):
        with open(x_file + '.{}'.format(i), 'rb') as f:
            seqs.append(np.array(pickle.load(f)))
    x_seq = np.concatenate(seqs, axis=0)
    # x_seq = np.array(pickle.load(open(x_file, 'rb')))
    tf.logging.info(f"load_data: {x_seq.shape}")
    return x_seq


def pickTwo(iVector, jVector, maxlen_seqs):
    for first in range(maxlen_seqs):
        for second in range(maxlen_seqs):
            if first == second: continue
            iVector.append(first)
            jVector.append(second)


def pickTwo_vi(Vts, vi, vj):
    num1_v1 = 0
    for first_v, v1 in enumerate(Vts):
        if v1 == [-1]:
            num1_v1 += 1
            continue
        seconds = []
        num1_v2 = 0
        for second_v, v2 in enumerate(Vts):
            if v2 != [-1]:
                seconds.append(v2)
                if num1_v1 == 0:
                    if second_v != first_v:
                        vi.append(first_v - num1_v1)
                        vj.append(second_v)
                else:
                    if second_v >= len(seconds) - num1_v2:
                        second_v = second_v - num1_v2
                        if second_v != first_v - num1_v1:
                            vi.append(first_v - num1_v1)
                            vj.append(second_v)
            else:
                num1_v2 += 1
                if num1_v2 == num1_v1:
                    seconds = Vts[:second_v + 1]
                else:
                    seconds = [0] * 100
                if num1_v2 > num1_v1:
                    break


def pad_matrix(seqs, maxlen_seqs):
    i_vec = []
    j_vec = []
    vi_vec = []
    vj_vec = []
    pickTwo_vi(seqs.tolist(), vi_vec, vj_vec)
    sents = []
    for idx, seq_id in enumerate(seqs):
        if not seq_id[0] == -1:
            seq_id_array = np.array(seq_id)
            # seq_id_array_1=(seq_id_array+np.ones_like(seq_id_array))
            sents.append(seq_id_array)
            pickTwo(i_vec, j_vec, maxlen_seqs)
    # sampled_cnt = min(len(i_vec), 30)
    # indices = np.random.choice(range(len(i_vec)), sampled_cnt)
    # indices = range(len(i_vec))
    # i_vec = np.asarray(i_vec)[indices].tolist()
    # j_vec = np.asarray(j_vec)[indices].tolist()
    X = np.zeros([len(sents), maxlen_seqs], np.int32)
    for i, x in enumerate(sents):
        X[i] = np.lib.pad(x, [0, maxlen_seqs - len(x)], 'constant', constant_values=(0, 0))
    return X, i_vec, j_vec, vi_vec, vj_vec


def model_train(model, saver, hp):
    for epoch in range(hp.max_epoch):
        tf.logging.info('epoch %d' % (epoch + 1))
        avg_cost = 0.
        x_seq = load_data(hp.data_path, hp.n_split)
        total_batch = int(np.ceil(len(x_seq) / hp.batch_size))
        for index in range(total_batch):
            x_batch = x_seq[index * hp.batch_size: (index + 1) * hp.batch_size]
            x, i_vec, j_vec, vi_vec, vj_vec = pad_matrix(x_batch, hp.maxlen_seqs)
            if len(i_vec) <= 0:
                continue
            vi_vec = np.expand_dims(vi_vec, 1)
            vj_vec = np.expand_dims(vj_vec, 1)
            cost = model.partial_fit(x=x, i_vec=i_vec, j_vec=j_vec, vi=vi_vec, vj=vj_vec)
            avg_cost += cost / len(x_seq) * hp.batch_size
            if index % 5000 == 0:
                avg_cost_batch = avg_cost / (index + 1)
                tf.logging.info(f"Epoch: {epoch + 1}, Index: {index}, avg_cost={avg_cost_batch}")
        if epoch % hp.display_step == 0:
            tf.logging.info(f"Epoch: {epoch + 1}, cost={avg_cost}")
        save_path = hp.save_model_path
        if os.path.exists(save_path):
            path = os.path.join(save_path, 'Lei4Cov')
        else:
            os.makedirs(save_path)
            path = os.path.join(save_path, 'Lei4Cov')
        saver.save(sess=model.sess, save_path=path, global_step=epoch)


def get_code_representation(model, saver, dirpath, dict_types_file, entity_embedding_path):
    ckpt = tf.train.get_checkpoint_state(dirpath)
    if ckpt and ckpt.model_checkpoint_path:
        saver.restore(model.sess, ckpt.model_checkpoint_path)
        embeddings = model.get_weights_embeddings()
        dict = {}
        for k, v in enumerate(embeddings):
            dict[k] = v
        file = open(entity_embedding_path, 'wb')
        pickle.dump(dict, file)
        file.close()
    else:
        print('ERROR')


def main(_):
    hparams = Hparams()
    parser = hparams.parser
    hp = parser.parse_args()
    n_input = 0
    with open(hp.entity_encode_file, 'r') as f:
        lines = f.readlines()
        n_input += len(lines)
    tf.logging.info(f"n_input: {n_input}")
    model = Lei4Cov(n_input=n_input, d_model=hp.d_model, batch_size=hp.batch_size,
                    maxseq_len=hp.maxlen_seqs, d_ff=hp.d_ff, num_blocks=hp.num_blocks,
                    num_heads=hp.num_heads, dropout_rate=hp.dropout_rate)
    saver = tf.train.Saver()
    model_train(model, saver, hp)
    get_code_representation(model, saver, hp.save_model_path, hp.dict_types_path, hp.entity_embedding_path)
    import datetime
    print(datetime.datetime.now())


if __name__ == "__main__":
    tf.app.run()
