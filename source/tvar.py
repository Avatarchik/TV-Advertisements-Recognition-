from typing import Tuple

import cv2
import ntpath
import os
import numpy as np
from database_sql import database
from sys import getsizeof
import json
import time
from datetime import datetime


class TAR(object):
    def __init__(self):
        self.db = database("127.0.0.1", "root", "", "TvAdsReco")
        self.conn = self.db.connect()

    @staticmethod
    def Json_encode(numpy1, numpy2):
        return json.dumps(numpy1.tolist()), json.dumps(numpy2.tolist())

    @staticmethod
    def Json_decode(frame_descriptor):
        """ """
        return np.array(json.loads("".join(frame_descriptor)), dtype=np.uint8)

    @staticmethod
    def frames_hash(frame1, frame2, hashSize=8):
        """image should be black and white"""
        frame1 = cv2.resize(frame1, (
            426, 240))  # Todo rajouter une fonction qui convertit tous les fichiers en mp4 et resize en (426, 240).
        resized1 = cv2.resize(frame1, (hashSize + 1, hashSize))
        diff1 = resized1[:, 1:] > resized1[:, :-1]
        frame2 = cv2.resize(frame2, (
            426, 240))  # Todo rajouter une fonction qui convertit tous les fichiers en mp4 et resize en (426, 240).
        resized2 = cv2.resize(frame2, (hashSize + 1, hashSize))
        diff2 = resized2[:, 1:] > resized2[:, :-1]
        return sum([2 ** i for (i, v) in enumerate(diff1.flatten()) if v]), sum(
            [2 ** i for (i, v) in enumerate(diff2.flatten()) if v])

    @staticmethod
    def get_frames(cap):
        cap.set(1, 1)
        _, first_frame = cap.read()
        cap.set(1, cap.get(cv2.CAP_PROP_FRAME_COUNT) - 25)
        _, last_frame = cap.read()
        return cv2.cvtColor(first_frame, cv2.COLOR_BGR2GRAY), cv2.cvtColor(last_frame, cv2.COLOR_BGR2GRAY)

    @staticmethod
    def create_descriptor(frame, nfeatures=100):
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        orb = cv2.ORB_create(nfeatures)
        _, des_frame = orb.detectAndCompute(frame, None)
        return des_frame

    @staticmethod
    def found_match(des_frame, des_current_frame):
        bf = cv2.BFMatcher(cv2.NORM_HAMMING)
        matches = bf.knnMatch(des_frame, des_current_frame, k=2)
        good = []
        for m, n in matches:
            if m.distance < 0.80 * n.distance:
                good.append([m])
        threshold = len(good) / len(des_frame)
        return threshold

    @staticmethod
    def read_video(cap):
        _, current_frame = cap.read()
        # current_frame = cv2.cvtColor(current_frame, cv2.COLOR_BGR2GRAY)
        cv2.imshow('frame', current_frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            exit()
        return current_frame

    def extract_des_file(self, path_file):
        """ Extract the descriptors of the first and the last frame from a given ads path"""
        """last frame"""
        orb = cv2.ORB_create(nfeatures=100)
        cap = cv2.VideoCapture(path_file)
        first_frame, last_frame = self.get_frames(cap)
        """ Wrinting the frames in frames directory """
        ads = os.path.basename(path_file)
        cv2.imwrite(
            "/Users/macbookpro/PycharmProjects/TV-Advertisements-Recognition-/frames/" + ads + "_" + "first_frame.jpeg",
            first_frame)
        cv2.imwrite(
            "/Users/macbookpro/PycharmProjects/TV-Advertisements-Recognition-/frames/" + ads + "_" + "last_frame.jpeg",
            last_frame)
        first_frame_hash, last_frame_hash = self.frames_hash(first_frame, last_frame)
        _, des_last_frame = orb.detectAndCompute(last_frame, None)
        _, des_first_frame = orb.detectAndCompute(first_frame, None)
        hash_file = np.int(str(first_frame_hash) + str(last_frame_hash))
        duration = round(cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS), 3)

        # cv2.imshow("as", first_frame)
        # while True:
        #     ch = 0xFF & cv2.waitKey(1)  # Wait for a second
        #     if ch == 27:
        #         break
        return des_first_frame, des_last_frame, duration, hash_file

    def extract_des_folder(self, path):
        start = time.time()
        list_ads = os.listdir(path)
        if '.DS_Store' in list_ads:
            list_ads.remove('.DS_Store')
        for ads in list_ads:
            des_first_frame, des_last_frame, duration, hash_file = self.extract_des_file(
                path + "/" + ads)
            if self.db.check_duplicate(hash_file):
                print("the hash of {} already exists".format(ads))
            else:
                des_first_frame, des_last_frame = self.Json_encode(des_first_frame, des_last_frame)
                self.db.insert_advertisement(ads, path + "/" + ads, des_first_frame, des_last_frame,
                                             duration, hash_file)
                print("The advertisement {} was added {} seconds".format(ads, time.time() - start))

        print("All advertisements have been added in {} seconds".format(time.time() - start))

    def found_first_match(self, current_frame, column="ff_descriptor", thresh=0.80):
        des_current_frame = self.create_descriptor(current_frame)
        id_ads = None
        for ads in self.db.get_all_advertisements(column):
            # print(ads[0])
            # print("/n")
            # print(ads)
            # print("/n")
            # print(len(self.db.get_all_advertisements(column)))
            des_frame = self.Json_decode(ads[1])
            # print(des_frame)
            # print("/n")
            # print(des_current_frame)
            threshold = self.found_match(des_frame, des_current_frame)
            if threshold > thresh:
                id_ads = ads[0]
                # print("found match")
        return id_ads  # todo le probleme est dans le None

    def found_last_des(self, id_ads, current_frame, thresh=0.80):
        # des_current_frame = self.create_descriptor(current_frame)
        des_last_frame = self.db.get_advertisement_des(id_ads)
        des_last_frame = self.Json_decode(des_last_frame)
        # threshold = self.found_match(des_last_frame, des_current_frame)
        # id_ad = None
        # print(threshold)
        # if threshold > thresh:
        #     id_ad = id_ads  # Todo inscrire dans la bdd
        #     print("last frame found")
        return des_last_frame

    def recognize(self, path_file):
        cap = cv2.VideoCapture(path_file)
        bf = cv2.BFMatcher(cv2.NORM_HAMMING)
        count = 0
        try:
            while True:
                count = count+1
                current_frame = self.read_video(cap)
                id_ads = self.found_first_match(current_frame)
                print("reading ")
                if id_ads is not None:
                    print(time.time())
                    des_last_frame = self.found_last_des(id_ads, current_frame)
                    while True:
                        count = count + 1
                        print("Looking for the last frame in",count,"/")
                        current_frame = self.read_video(cap)
                        des_current_frame = self.create_descriptor(current_frame)
                        """"""
                        matches = bf.knnMatch(des_current_frame, des_last_frame, k=2)
                        good = []
                        for m, n in matches:
                            if m.distance < 0.80 * n.distance:
                                good.append([m])
                        threshold = len(good) / len(des_last_frame)
                        if threshold > .80:
                            print("Last frame found in {}".format(count))
                            break
                        """"""
                        # threshold = self.found_match(des_last_frame, des_current_frame)
                        # if threshold > .80:
                        #     print("Last frame found in {}".format(count))
                        #     break
                        """"""
        except:
            print("Finish reading")


        # return print("start time, end time ")

detecteur = TAR()
# detecteur.extract_des_folder("/Users/macbookpro/PycharmProjects/TV-Advertisements-Recognition-/videos")
# detecteur.recognize("../videos/Dima Ooredoo خير بدل جدد.mp4")
# detecteur.recognize("../videos/DjezzyOredoo.mp4")
# detecteur.recognize("../videos/lactofibre-rkm-1-fy-algzayr.mp4")
# detecteur.recognize("../videos/mobylys-ytmn-lkm-aayd-mbark-o-kl-aaam-o-antm-bkhyr-sh-aaydkm-aayd-aladh-almbark.mp4")
detecteur.recognize("/Users/macbookpro/PycharmProjects/TV-Advertisements-Recognition-/stream/DjezzyOredoo.m3u8")
# DjezzyOredoo.mp4
# id_ads = 1
# des_last_frame = detecteur.db.get_advertisement_des(id_ads)
# des_last_frame = detecteur.Json_decode(des_last_frame)
# img = cv2.imread("/Users/macbookpro/PycharmProjects/TV-Advertisements-Recognition-/frames/mobylys-ytmn-lkm-aayd-mbark-o-kl-aaam-o-antm-bkhyr-sh-aaydkm-aayd-aladh-almbark.mp4_last_frame.jpeg")
# detecteur.found_last_des(4, img)

# cap = cv2.VideoCapture("../videos/mobylys-ytmn-lkm-aayd-mbark-o-kl-aaam-o-antm-bkhyr-sh-aaydkm-aayd-aladh-almbark.mp4")
# #
# cap.set(cv2.CAP_PROP_FPS, 35)
# fps = int(cap.get(5))
# print("fps:", fps, cap.get(cv2.CAP_PROP_FRAME_COUNT))
# while True:
#     ret, frame = cap.read()
#     cv2.imshow("A", frame)
#     ch = 0xFF & cv2.waitKey(55) # Wait for a second
#     if ch == 27:
#         break
