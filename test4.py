import sys
import pygame
from pygame.locals import *
import numpy as np
import time
import ctypes
import os   

from PIL import Image

import math

def isPressed(key):
    return(bool(ctypes.windll.user32.GetAsyncKeyState(key)&0x8000))

#ReLU関数
def relu(x):
    return np.maximum(0, x) #0とxを比較して大きい方の数値を返す

class env:#システム系
    D=0x44
    A=0x41
    SPACE=0x20

    WIDTH = 1700
    HEIGHT = 900

    BLOCKSIZE_X = WIDTH/17
    BLOCKSIZE_Y = HEIGHT/9

    BLOCKSIZE_X_H = (WIDTH/17)/2
    BLOCKSIZE_Y_H = (HEIGHT/9)/2


    NAMELIST = ['air','stone','grass','dirt','cobblestone','planks','sapling','bedrock','water','lava','gold_ore','iron_ore','coal_ore','log'
    ,'leaves','bed','crafting_table','diamond_ore','iron_shovel','iron_pickaxe','iron_axe','apple','iron_sword','wooden_sword'
    ,'wooden_shovel','wooden_pickaxe','wooden_axe','stone_sword','stone_shovel','stone_pickaxe','stone_axe','stick','iron_helmet'
    ,'iron_chestplate','iron_leggings','iron_boots','diamond_helmet','diamond_chestplate','diamond_leggings','diamond_boots','porkchop']


    SKIN = ([247,195,169])
    AIR = ([131,166,255])
    def __init__(self):
        self._reset()
    def _reset(self):
        # 諸々の変数を初期化する
        #ロードされたチャンクを格納
        self.land = np.zeros((128,128))
        #プレーヤーの位置情報などを格納
        self.player = np.zeros(2,dtype='int64')#x,y
        #entity = np.zeros()#ID,x,y
        #描画用のRGBを格納
        self.num_rgb = np.zeros((17,9,3),dtype=np.uint8)#x,y,RGB
        self.observation = np.zeros((17,9))
        self.view = np.zeros((17,9))
        #ロードするかしないか判定用
        self.load_able = 2
        #移動している方向格納 0右1左3なし
        self.move_direction = 3
        #空中に浮いている時間を格納(落下速度計算用)
        self.flying_time = 0
        #ステップ数格納
        self.steps = 0
        #持っているアイテムIDリスト
        self.holding_item = 1

        try:
            self.player = np.load('./saves/world1/playerdata/location.npy')
        except FileNotFoundError:#プレーヤーのデータがなかった場合0 64
            self.player[1] = 64
        self.get_chunkID()
        try:#セーブデータロード
            if self.player[0]%64 < 32:#プレーヤーの場所は2
                self.load(0,self.chunk_ID-1)
                self.load(1,self.chunk_ID)
            else:#プレーヤーの場所は1
                self.load(0,self.chunk_ID)
                self.load(1,self.chunk_ID+1)
        except FileNotFoundError:
            #初回ロード地形生成
            self.make_world(0)
            self.make_world(1)

        #ここから下は人がプレイするときだけ使う
        self.actions = np.zeros(16)

        #AIがプレイするときはここから消してrenderの一番上に持っていく
        if self.steps == 0:#一度目の処理なので描画初期化
            # Pygameを初期化
            icon = pygame.image.load("./texture/crafting_table.png") #画像を読み込む
            pygame.init()
            self.screen = pygame.display.set_mode((self.WIDTH, self.HEIGHT))
            pygame.display.set_caption("2Dminecraft-gym-v0")              # タイトルバーに表示する文字
            pygame.display.set_icon(icon)
            self.font = pygame.font.Font(None, 15)               # フォントの設定(55px)
            self.fps_clock = pygame.time.Clock()

            self.TEXTURE = np.zeros((((16,16,4,41))))
            i = 0
            for name in self.NAMELIST:
                image = Image.open('./texture/'+name+'.png')
                if np.array(image).shape[2] == 3:
                    image.putalpha(0)#アルファチャンネルがないやつに追加する
                image = np.flipud(np.rot90(np.array(image)))
                self.TEXTURE[:,:,:,i] = np.array(image)
                i = i + 1
            self.steve = pygame.image.load('./texture/steve.png').convert_alpha()

            self.right = True

    def _step(self):#ステップ処理
        #時間に応じて空の色変更 時間はAIの入力に入れる

        self.get_chunkID()
        self.load_chunk()

        self.get_chunk_player_x()
        self.fall()

        self.get_view()

        self.get_action()
        self.execute_action()

        self.get_view()
        self._render()

        #ステップすすめる
        self.steps += 1
    def _render(self):
        '''
        if self.steps == 0:#一度目の処理なので描画初期化
            # Pygameを初期化
            icon = pygame.image.load("./texture/crafting_table.png") #画像を読み込む
            pygame.init()
            self.screen = pygame.display.set_mode((self.WIDTH, self.HEIGHT))
            pygame.display.set_caption("2Dminecraft-gym-v0")              # タイトルバーに表示する文字
            pygame.display.set_icon(icon)
            self.font = pygame.font.Font(None, 15)               # フォントの設定(55px)
            self.fps_clock = pygame.time.Clock()
        '''
        '''
        if self.steps%1280 < 640:#320以下は昼
            self.BLOCK_DATA[0,:3] = [131,166,255]
        if self.steps%1280 >= 640:#320以下は昼
            self.BLOCK_DATA[0,:3] = [0,0,0]'''

        self.view = np.fliplr(self.view)#上下反転

        for x in range(17):
            for y in range(9):
                texture = self.TEXTURE[:,:,:3,int(self.view[x][y])]
                texture[:,:,0] = np.where(texture[:,:,0] == 0 ,131 ,texture[:,:,0])
                texture[:,:,1] = np.where(texture[:,:,1] == 0 ,166 ,texture[:,:,1])
                texture[:,:,2] = np.where(texture[:,:,2] == 0 ,255 ,texture[:,:,2])
                texture = pygame.surfarray.make_surface(texture)
                texture = pygame.transform.scale(texture, (math.ceil(self.BLOCKSIZE_X), math.ceil(self.BLOCKSIZE_Y))) #リサイズ
                self.screen.blit(texture, (self.BLOCKSIZE_X*x, self.BLOCKSIZE_Y*y))

        #プレーヤー描画
        #self.num_rgb[8,3:5,:] = self.SKIN
        if self.actions[1] == 1 and self.right == True:#左に進む
            self.steve = pygame.transform.flip(self.steve,1,0)
            self.right = False
        if self.actions[0] == 1 and self.right == False:#右に進む
            self.steve = pygame.transform.flip(self.steve,1,0)
            self.right = True
        self.steve = pygame.transform.scale(self.steve, (math.ceil(self.BLOCKSIZE_X/1.9), math.ceil(self.BLOCKSIZE_Y*2))) #リサイズ
        self.screen.blit(self.steve, (self.WIDTH/2-((self.BLOCKSIZE_X/1.9)/2),self.HEIGHT/2-(self.BLOCKSIZE_Y/2)))

        self.landrgb = np.fliplr(self.land)#上下反転
        self.landrgb = pygame.surfarray.make_surface(self.landrgb)
        
        text = self.font.render('X:'+str(self.player[0])+' Y:'+str(self.player[1])+' C:'+str(self.chunk_ID)+' I:'+str(self.holding_item)+'I:'+str(self.steps), True, (255,255,255))   # デバック情報表示
        self.screen.blit(self.landrgb, (0, 0))
        self.screen.blit(text, [10, 10])# 文字列の表示位置
        pygame.display.update()  # 画面を更新

        self.fps_clock.tick(32)
    def close(self):
        pygame.quit()

    def seed(self):
        pass

    def _get_reward(self):
        pass

    def get_view(self):
        if self.player[1]-3 < 0:
            self.view[:,9-relu(6+self.player[1]):] = self.land[self.chunk_player_x-8:self.chunk_player_x+9,relu(self.player[1]-3):relu(self.player[1]+6)].copy()
            self.view[:,:9-relu(6+self.player[1])] = 0
        elif self.player[1]+6 > 128:
            self.view[:,:131-self.player[1]] = self.land[self.chunk_player_x-8:self.chunk_player_x+9,self.player[1]-3:self.player[1]+6].copy()
            self.view[:,131-self.player[1]:] = 0
        else:
            self.view = self.land[self.chunk_player_x-8:self.chunk_player_x+9,self.player[1]-3:self.player[1]+6].copy()

    def make_world(self,chunk_ID):#ワールド生成 chunk_IDは生成する予定のチャンクのID chunk0/chunk1
        #後々変更
        if chunk_ID == 0:
            self.land[:64,:][:,:69] = 2
            self.land[:64,:][:,69:] = 0
            self.land[:64,:][:,0] = 7
        if chunk_ID == 1:
            self.land[64:,:][:,:69] = 2
            self.land[64:,:][:,69:] = 0
            self.land[64:,:][:,0] = 7

    def save(self,chunk_ID,land_ID):
        if chunk_ID == 0:
            np.save('./saves/world1/map/'+str(land_ID)+'.npy', self.land[:64,:])
        elif chunk_ID == 1:
            np.save('./saves/world1/map/'+str(land_ID)+'.npy', self.land[64:,:])

    def load(self,chunk_ID,land_ID):#chunk_IDは代入する予定のチャンクのID chunk0/chunk1
        if chunk_ID == 0:
            self.land[:64,:] = np.load('./saves/world1/map/'+str(land_ID)+'.npy')
        elif chunk_ID == 1:
            self.land[64:,:] = np.load('./saves/world1/map/'+str(land_ID)+'.npy')
    def get_action(self):#人間がプレイするとき用にactinをゲットする
        self.actions[:] = 0#右左ジャンプ下左下右下左横右横右上左上左上上上々右上上右クリック
        
        if isPressed(self.D):#右
            self.actions[0] = 1
        if isPressed(self.A):#左
            self.actions[1] = 1
        if isPressed(self.SPACE):#ジャンプ
            self.actions[2] = 1
        for event in pygame.event.get():
            # マウスクリックで画像移動
            if self.player[1] >= 0:
                if event.type == MOUSEBUTTONDOWN and event.button == 1:#129から破壊不能 左クリック
                    mouse_x, mouse_y = event.pos
                    self.actions[13] = 0
                    if self.BLOCKSIZE_X*8<mouse_x<self.BLOCKSIZE_X*9 and self.BLOCKSIZE_Y*6<mouse_y<self.BLOCKSIZE_Y*7:
                        self.actions[3] = 1
                    if self.BLOCKSIZE_X*7<mouse_x<self.BLOCKSIZE_X*8 and self.BLOCKSIZE_Y*6<mouse_y<self.BLOCKSIZE_Y*7:
                        self.actions[4] = 1
                    if self.BLOCKSIZE_X*9<mouse_x<self.BLOCKSIZE_X*10 and self.BLOCKSIZE_Y*6<mouse_y<self.BLOCKSIZE_Y*7:
                        self.actions[5] = 1
                    if self.BLOCKSIZE_X*7<mouse_x<self.BLOCKSIZE_X*8 and self.BLOCKSIZE_Y*5<mouse_y<self.BLOCKSIZE_Y*6:
                        self.actions[6] = 1
                    if self.BLOCKSIZE_X*9<mouse_x<self.BLOCKSIZE_X*10 and self.BLOCKSIZE_Y*5<mouse_y<self.BLOCKSIZE_Y*6:
                        self.actions[7] = 1
                    if self.BLOCKSIZE_X*9<mouse_x<self.BLOCKSIZE_X*10 and self.BLOCKSIZE_Y*4<mouse_y<self.BLOCKSIZE_Y*5:
                        self.actions[8] = 1
                    if self.BLOCKSIZE_X*7<mouse_x<self.BLOCKSIZE_X*8 and self.BLOCKSIZE_Y*4<mouse_y<self.BLOCKSIZE_Y*5:
                        self.actions[9] = 1
                    if self.BLOCKSIZE_X*7<mouse_x<self.BLOCKSIZE_X*8 and self.BLOCKSIZE_Y*3<mouse_y<self.BLOCKSIZE_Y*4:
                        self.actions[10] = 1
                    if self.BLOCKSIZE_X*8<mouse_x<self.BLOCKSIZE_X*9 and self.BLOCKSIZE_Y*3<mouse_y<self.BLOCKSIZE_Y*4:
                        self.actions[11] = 1
                    if self.BLOCKSIZE_X*9<mouse_x<self.BLOCKSIZE_X*10 and self.BLOCKSIZE_Y*3<mouse_y<self.BLOCKSIZE_Y*4:
                        self.actions[12] = 1

                if event.type == MOUSEBUTTONDOWN and event.button == 3:#右クリック
                    mouse_x, mouse_y = event.pos
                    self.actions[13] = 1
                    if self.BLOCKSIZE_X*8<mouse_x<self.BLOCKSIZE_X*9 and self.BLOCKSIZE_Y*6<mouse_y<self.BLOCKSIZE_Y*7:
                        self.actions[3] = 1
                    if self.BLOCKSIZE_X*7<mouse_x<self.BLOCKSIZE_X*8 and self.BLOCKSIZE_Y*6<mouse_y<self.BLOCKSIZE_Y*7:
                        self.actions[4] = 1
                    if self.BLOCKSIZE_X*9<mouse_x<self.BLOCKSIZE_X*10 and self.BLOCKSIZE_Y*6<mouse_y<self.BLOCKSIZE_Y*7:
                        self.actions[5] = 1
                    if self.BLOCKSIZE_X*7<mouse_x<self.BLOCKSIZE_X*8 and self.BLOCKSIZE_Y*5<mouse_y<self.BLOCKSIZE_Y*6:
                        self.actions[6] = 1
                    if self.BLOCKSIZE_X*9<mouse_x<self.BLOCKSIZE_X*10 and self.BLOCKSIZE_Y*5<mouse_y<self.BLOCKSIZE_Y*6:
                        self.actions[7] = 1
                    if self.BLOCKSIZE_X*9<mouse_x<self.BLOCKSIZE_X*10 and self.BLOCKSIZE_Y*4<mouse_y<self.BLOCKSIZE_Y*5:
                        self.actions[8] = 1
                    if self.BLOCKSIZE_X*7<mouse_x<self.BLOCKSIZE_X*8 and self.BLOCKSIZE_Y*4<mouse_y<self.BLOCKSIZE_Y*5:
                        self.actions[9] = 1
                    if self.BLOCKSIZE_X*7<mouse_x<self.BLOCKSIZE_X*8 and self.BLOCKSIZE_Y*3<mouse_y<self.BLOCKSIZE_Y*4:
                        self.actions[10] = 1
                    if self.BLOCKSIZE_X*8<mouse_x<self.BLOCKSIZE_X*9 and self.BLOCKSIZE_Y*3<mouse_y<self.BLOCKSIZE_Y*4:
                        self.actions[11] = 1
                    if self.BLOCKSIZE_X*9<mouse_x<self.BLOCKSIZE_X*10 and self.BLOCKSIZE_Y*3<mouse_y<self.BLOCKSIZE_Y*4:
                        self.actions[12] = 1

                if event.type == MOUSEBUTTONDOWN and event.button == 4:#ホイールを上スクロール
                    self.actions[14] = 1
                if event.type == MOUSEBUTTONDOWN and event.button == 5:#ホイールを下にスクロール
                    self.actions[15] = 1

            if event.type == QUIT:  # 閉じるボタンが押されたら終了
                #セーブ
                np.save('./saves/world1/playerdata/location.npy', self.player)
                if self.player[0]%64 < 32:
                    self.save(0,self.chunk_ID-1)
                    self.save(1,self.chunk_ID)
                else:
                    self.save(1,self.chunk_ID+1)
                    self.save(0,self.chunk_ID)
                pygame.quit()       # Pygameの終了(画面閉じられる)
                sys.exit()
        
    def execute_action(self):
        if self.actions[0] == 1:#右print(self.block_data(1,2))
            if self.block_data(1,0) == 0 and self.block_data(1,1) == 0:
                self.player[0] = self.player[0] + 1
                self.move_direction = 0
        if self.actions[1] == 1:#左
            if self.block_data(-1,0) == 0 and self.block_data(-1,1) == 0:
                self.player[0] = self.player[0] - 1
                self.move_direction = 1
        if self.actions[2] == 1:
            if self.block_data(0,2) == 0:
                if self.player[1] >= 0:
                    if self.flying_time == 0:#空中に浮いてない場合
                        self.player[1] = self.player[1] + 1

        if self.player[1] >= 0:
            if self.actions[13] == 0:#129から破壊不能
                if 0 <= self.player[1]-1 < 128:
                    if self.actions[3] == 1:
                        self.land[self.chunk_player_x,self.player[1]-1] = 0
                    if self.actions[4] == 1:
                        self.land[self.chunk_player_x-1,self.player[1]-1] = 0
                    if self.actions[5] == 1:
                        self.land[self.chunk_player_x+1,self.player[1]-1] = 0
                if 0 <= self.player[1] < 128:
                    if self.actions[6] == 1:
                        self.land[self.chunk_player_x-1,self.player[1]] = 0
                    if self.actions[7] == 1:
                        self.land[self.chunk_player_x+1,self.player[1]] = 0
                if 0 <= self.player[1]+1 < 128:
                    if self.actions[8] == 1:
                        self.land[self.chunk_player_x+1,self.player[1]+1] = 0
                    if self.actions[9] == 1:
                        self.land[self.chunk_player_x-1,self.player[1]+1] = 0
                if 0 <= self.player[1]+2 < 128:
                    if self.actions[10] == 1:
                        self.land[self.chunk_player_x-1,self.player[1]+2] = 0
                    if self.actions[11] == 1:
                        self.land[self.chunk_player_x,self.player[1]+2] = 0
                    if self.actions[12] == 1:
                        self.land[self.chunk_player_x+1,self.player[1]+2] = 0

            if self.actions[13] == 1:
                if 0 <= self.player[1]-1 < 128:
                    if self.actions[3] == 1:
                        if self.block_data(0,-1) == 0:
                            self.land[self.chunk_player_x,self.player[1]-1] = self.holding_item
                    if self.actions[4] == 1:
                        if self.block_data(-1,-1) == 0:
                            self.land[self.chunk_player_x-1,self.player[1]-1] = self.holding_item
                    if self.actions[5] == 1:
                        if self.block_data(1,-1) == 0:
                            self.land[self.chunk_player_x+1,self.player[1]-1] = self.holding_item
                if 0 <= self.player[1] < 128:
                    if self.actions[6] == 1:
                        if self.block_data(-1,0) == 0:
                            self.land[self.chunk_player_x-1,self.player[1]] = self.holding_item
                    if self.actions[7] == 1:
                        if self.block_data(1,0) == 0:
                            self.land[self.chunk_player_x+1,self.player[1]] = self.holding_item
                if 0 <= self.player[1]+1 < 128:
                    if self.actions[8] == 1:
                        if self.block_data(1,1) == 0:
                            self.land[self.chunk_player_x+1,self.player[1]+1] = self.holding_item
                    if self.actions[9] == 1:
                        if self.block_data(-1,1) == 0:
                            self.land[self.chunk_player_x-1,self.player[1]+1] = self.holding_item
                if 0 <= self.player[1]+2 < 128:
                    if self.actions[10] == 1:
                        if self.block_data(-1,2) == 0:
                            self.land[self.chunk_player_x-1,self.player[1]+2] = self.holding_item
                    if self.actions[11] == 1:
                        if self.block_data(0,2) == 0:
                            self.land[self.chunk_player_x,self.player[1]+2] = self.holding_item
                    if self.actions[12] == 1:
                        if self.block_data(1,2) == 0:
                            self.land[self.chunk_player_x+1,self.player[1]+2] = self.holding_item
            
            if self.actions[14] == 1:
                self.holding_item = self.holding_item + 1
            if self.actions[15] == 1:
                self.holding_item = self.holding_item - 1

            if self.holding_item < 1:#1以下になったら最後に戻る
                self.holding_item = 40
            if self.holding_item > 40:
                self.holding_item = 1

    def get_chunkID(self):
        self.chunk_ID = self.player[0]/64
        if self.chunk_ID < 0:#0以下だったら-1
            self.chunk_ID = int(self.chunk_ID) - 1
        else:
            self.chunk_ID = int(self.chunk_ID)

    def load_chunk(self):
        if self.player[0]%64 < 32:
            if self.load_able == 0 and self.move_direction == 1:#前が0だったとき境界線から左に動いたとこになるから左側のチャンクをロードする
                self.save(1,self.chunk_ID+1)
                self.land[64:,:] = self.land[:64,:]#左にあったものは右に
                try:
                    self.load(0,self.chunk_ID-1)
                except FileNotFoundError:
                    #地形生成
                    self.make_world(0)
            self.chunk_player_x = self.player[0]%64 + 64
            self.load_able = 1
        else:
            if self.load_able == 1 and self.move_direction == 0:#前が1だったとき境界線から右に動いたとこになるから右側のチャンクをロードする
                self.save(0,self.chunk_ID-1)
                self.land[:64,:] = self.land[64:,:]#右にあったものは左に
                try:
                    self.load(1,self.chunk_ID+1)
                except FileNotFoundError:
                    #地形生成
                    self.make_world(1)
            self.chunk_player_x = self.player[0]%64
            self.load_able = 0

    def get_chunk_player_x(self):
        if self.player[0]%64 < 32:
            self.chunk_player_x = self.player[0]%64 + 64
        else:
            self.chunk_player_x = self.player[0]%64

    def fall(self):
        #落下処理
        if self.player[1] >= 0:#岩盤より下は必ず落下
            if self.player[1] > 128:#128は127までずっとブロックがない
                if not self.flying_time == 0:#ジャンプしたときは落下しない
                    fall_y = self.player[1]#落下量を計算するためにプレーヤーのyの座標をfloatで格納する変数
                    fall_y = fall_y - (9.8 * (self.flying_time/32)**2 / 2)
                    if int(fall_y) > 127:#必ず落下可能
                        self.player[1] = int(fall_y)
                    else:
                        for y in range(int(fall_y),128)[::-1]:
                            if not self.land[self.chunk_player_x,y] == 0:#空気ブロックじゃなくなったら
                                self.player[1] = y + 1
                                break
                            if y <= int(fall_y):
                                self.player[1] = int(fall_y)
                self.flying_time = self.flying_time + 1
            elif self.land[self.chunk_player_x,self.player[1]-1] == 0:#下にブロックがない場合
                if not self.flying_time == 0:#ジャンプしたときは落下しない
                    fall_y = self.player[1]#落下量を計算するためにプレーヤーのyの座標をfloatで格納する変数
                    fall_y = fall_y - (9.8 * (self.flying_time/32)**2 / 2)
                    
                    for y in range(int(fall_y),self.player[1])[::-1]:
                        if not self.land[self.chunk_player_x,y] == 0:#空気ブロックじゃなくなったら
                            self.player[1] = y + 1
                            break
                        if y <= int(fall_y):
                            self.player[1] = int(fall_y)
                self.flying_time = self.flying_time + 1
            else:#着地0
                self.flying_time = 0
        else:#岩盤より下だったら永遠に落ちる
            fall_y = self.player[1]#落下量を計算するためにプレーヤーのyの座標をfloatで格納する変数
            fall_y = fall_y - (9.8 * (self.flying_time/32)**2 / 2)
            self.player[1] = int(fall_y)

    def obs(self):#描画する範囲の配列を返す
        pass
    def set_block(self,x,y):#ブロックを設置してワールドデータを改変する
        pass
    def block_data(self,x,y):#指定座標のブロックのデータを返す 0,-1はました 1,2 は右上
        return self.view[8+x][3+y]

#仮


mine = env()

while True:
    mine._step()
    