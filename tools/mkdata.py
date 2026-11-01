# -*- coding: utf-8 -*-
"""Generate plant-data.js (structure registry + roads + trees) for the Three.js project."""
import json, sys, math, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ENTS = json.load(open(r'D:\test\.dwgconv\out\entities.json', encoding='utf-8'))
ROADS = json.load(open(r'D:\test\.dwgconv\roads.json', encoding='utf-8'))

OUT = r'D:\test\src\3d-powerplant\plant-data.js'
os.makedirs(os.path.dirname(OUT), exist_ok=True)

# ---- 树木 (VEGTRE 块插入点) ----
trees = []
for e in ENTS:
    if e['type'] != 'INSERT':
        continue
    if 'VEGTRE' not in str(e.get('blockName', '')):
        continue
    p = e.get('position') or e.get('insertionPoint')
    if not p:
        continue
    x, y = round(p[0], 1), round(p[1], 1)
    if 2900800 < x < 2902800 and 2548300 < y < 2549800:
        trees.append([x, y])
print('trees', len(trees))

EST = '【图纸信息不足，尺寸为火电工程常规估算值，待复核】'

S = []
def add(**kw):
    d = dict(id=kw.pop('id'), code=kw.pop('code', ''), name=kw.pop('name'),
             cat=kw.pop('cat', 'main'), shape=kw.pop('shape'),
             x=kw.pop('x'), y=kw.pop('y'))
    d.update(kw)
    S.append(d)

# ============ 主厂房区 (二期 2×600MW, 编号取自图纸一览表) ============
add(id='ST-101', code='101', name='汽机房', cat='main', shape='box', x=2901755.0, y=2549219.3,
    w=175, d=34, h=36, rot=0, area=6020,
    note='单层装配式厂房，跨度34m，两台汽轮发电机组共用；布置于主厂房北侧，A排外侧为主变压器场',
    src='位置：图纸编号101标注点；平面尺寸：按一览表面积6020m²与汽机房常规跨度反算(175×34.4m)')
add(id='ST-102', code='102', name='除氧及煤仓间', cat='main', shape='box', x=2901756.0, y=2549192.4,
    w=175, d=13.2, h=46, rot=0, area=2300,
    note='除氧间+煤仓间合并布置，煤斗层标高约+38.00m',
    src='位置：图纸编号102标注点；面积取自一览表2300m²')
add(id='ST-103A', code='103', name='1#锅炉房（锅炉）', cat='main', shape='box', x=2901714.2, y=2549152.1,
    w=47.1, d=64.4, h=75, rot=0, area=3033,
    note='锅炉钢架+炉膛+尾部烟道；图纸矩形轮廓量测47.1×64.4m（一览表两台合计8840m²）',
    src='平面轮廓：图纸实测矩形 (2901690.6,2549119.9)-(2901737.7,2549184.2)')
add(id='ST-103B', code='103', name='2#锅炉房（锅炉）', cat='main', shape='box', x=2901805.3, y=2549152.1,
    w=47.1, d=64.4, h=75, rot=0, area=3033,
    note='与1#锅炉房对称布置',
    src='平面轮廓：图纸实测矩形 (2901781.8,2549119.9)-(2901828.9,2549184.2)')
add(id='ST-104A', code='104', name='1#送风机支架', cat='main', shape='gantry', x=2901704.5, y=2549114.1,
    w=18, d=12, h=12, rot=0, area=390, note='钢结构支架，上布置送风机，配置检修通道',
    src='位置：图纸编号104标注点；尺寸为常规估算值' + EST)
add(id='ST-104B', code='104', name='2#送风机支架', cat='main', shape='gantry', x=2901801.9, y=2549114.1,
    w=18, d=12, h=12, rot=0, area=390, note='与1#对称', src='同104；' + EST)
add(id='ST-105A', code='105', name='1#电除尘器', cat='main', shape='box', x=2901704.0, y=2549078.3,
    w=40, d=35, h=30, rot=0, area=1400, note='双室四电场静电除尘器，钢支架+灰斗',
    src='位置：图纸编号105标注点；平面按2820m²两台均分估算' + EST)
add(id='ST-105B', code='105', name='2#电除尘器', cat='main', shape='box', x=2901809.2, y=2549078.3,
    w=40, d=35, h=30, rot=0, area=1400, note='与1#对称', src='同105；' + EST)
add(id='ST-106A', code='106', name='1#引风机支架', cat='main', shape='gantry', x=2901718.2, y=2549056.2,
    w=26, d=18, h=14, rot=0, area=460, note='钢结构支架，布置引风机及烟道接口',
    src='位置：图纸编号106标注点；' + EST)
add(id='ST-106B', code='106', name='2#引风机支架', cat='main', shape='gantry', x=2901813.9, y=2549057.4,
    w=26, d=18, h=14, rot=0, area=460, note='与1#对称', src='同106；' + EST)
add(id='ST-107', code='107', name='烟道', cat='main', shape='duct', x=2901733.5, y=2549047.9,
    w=30, d=14, h=12, rot=0, area=750, note='引风机出口至烟囱的钢烟道（矩形断面），架空敷设',
    src='位置：图纸编号107标注点；断面为常规估算值' + EST)
add(id='ST-108', code='108', name='烟囱', cat='main', shape='chimney', x=2901752.8, y=2549050.0,
    d=16.4, h=210, rot=0, area=210,
    note='单筒式钢筋混凝土烟囱，出口内径约8.5m；红白相间航空标志漆分段（每30m）。一览表占地面积210m²→底径约16.4m',
    src='位置：图纸编号108标注点；高210m、底径16.4m按一览表面积与600MW机组常规参数取值' + EST)
add(id='ST-109', code='109', name='空压机及电除尘配电室', cat='main', shape='box', x=2901756.6, y=2549072.9,
    w=30, d=20, h=12, rot=0, area=600, note='两层框架结构，含空压机房与电除尘配电装置',
    src='位置：图纸编号109标注点；' + EST)
add(id='ST-110A', code='110', name='1#主变压器', cat='electrical', shape='transformer', x=2901699.7, y=2549244.5,
    w=14, d=11, h=12, rot=0, area=200, note='三相双绕组强迫油循环变压器，设事故油池与防火墙',
    src='位置：图纸编号110标注点；' + EST)
add(id='ST-110B', code='110', name='2#主变压器', cat='electrical', shape='transformer', x=2901790.9, y=2549244.6,
    w=14, d=11, h=12, rot=0, area=200, note='与1#对称', src='同110；' + EST)
add(id='ST-111A', code='111', name='1#厂用变压器', cat='electrical', shape='transformer', x=2901727.3, y=2549245.6,
    w=10, d=9, h=10, rot=0, area=95, note='高压厂用变压器', src='位置：图纸编号111标注点；' + EST)
add(id='ST-111B', code='111', name='2#厂用变压器', cat='electrical', shape='transformer', x=2901818.8, y=2549244.7,
    w=10, d=9, h=10, rot=0, area=95, note='与1#对称', src='同111；' + EST)
add(id='ST-112', code='112', name='防火墙（三座）', cat='electrical', shape='box', x=2901735.9, y=2549234.4,
    w=30, d=0.5, h=6, rot=0, area=45, note='主变之间及主变与厂用变之间的防火隔墙，共三座',
    src='位置：图纸编号112标注点；' + EST)
add(id='ST-113', code='113', name='备用变压器', cat='electrical', shape='transformer', x=2901833.5, y=2549244.9,
    w=10, d=9, h=10, rot=0, area=110, note='启动/备用变压器', src='位置：图纸编号113标注点；' + EST)
add(id='ST-114', code='114', name='石灰石粉仓', cat='aux', shape='tank', x=2901785.4, y=2548958.2,
    d=14, h=26, rot=0, area=160, note='脱硫用石灰石粉仓（钢板仓），下设卸料间',
    src='位置：图纸编号114标注点；' + EST)
add(id='ST-117', code='117', name='变压器事故油池', cat='electrical', shape='pit', x=2901746.4, y=2549255.6,
    w=8, d=6, h=1, rot=0, area=50, note='地下式油池，池顶设格栅', src='位置：图纸编号117标注点；' + EST)
add(id='ST-118', code='118', name='透平机事故油池', cat='main', shape='pit', x=2901745.5, y=2549243.5,
    w=7, d=6, h=1, rot=0, area=40, note='汽轮机事故排油用地下油池', src='位置：图纸编号118标注点；' + EST)
add(id='ST-119', code='119', name='500kV配电装置', cat='electrical', shape='switchyard', x=2901759.8, y=2549379.5,
    w=200, d=131, h=26, rot=0, area=26300,
    note='户外式500kV GIS/敞开式配电装置，构架立柱+横梁，含软母线、隔离开关与支柱绝缘子；场地围栅690m',
    src='位置：图纸编号119标注点；26300m²按一览表；场地按主厂房纵向200m布置' + EST)
add(id='ST-120', code='120', name='连接天桥', cat='main', shape='gallery', x=2901855.9, y=2549182.2,
    w=60, d=4.5, h=10, rot=0, area=160, note='主厂房与500kV配电装置间的通行天桥（钢结构封闭廊道）',
    src='位置：图纸编号120标注点；' + EST)
add(id='ST-123', code='123', name='传达门卫', cat='aux', shape='box', x=2901655.6, y=2549010.3,
    w=8, d=5, h=4, rot=0, area=20, note='厂区主入口门卫及道闸', src='位置：图纸编号123标注点；' + EST)

# ============ 冷却塔及循环水系统 ============
add(id='ST-127A', code='127', name='1#循环水冷却塔', cat='cooling', shape='hyperbolic', x=2901391.4, y=2549265.3,
    d=102, h=130, rot=0, area=8170,
    note='双曲线逆流式自然通风冷却塔，淋水面积6000m²；喉部直径约0.72D，底部进风口高约8m',
    src='圆心与半径由图纸两条bulge=1半圆多段线反算得出，半径51m（直径102m）；高度130m按淋水面积6000m²常规取值' + EST)
add(id='ST-127B', code='127', name='2#循环水冷却塔', cat='cooling', shape='hyperbolic', x=2901541.1, y=2549374.0,
    d=102, h=130, rot=0, area=8170, note='与1#同型，两塔间距约185m',
    src='同上，圆心(2901541.1,2549374.0)，半径51m')
add(id='ST-126', code='126', name='循环水泵房', cat='cooling', shape='box', x=2901459.1, y=2549316.8,
    w=45, d=21, h=14, rot=0, area=950, note='地下/半地下泵房，内设循环水泵及旋转滤网',
    src='位置：图纸编号126标注点；面积取自一览表950m²，按45×21m布置')
add(id='ST-129', code='129', name='循环水泵加氯间', cat='cooling', shape='box', x=2901429.7, y=2549367.6,
    w=15, d=8, h=6, rot=0, area=120, note='循环水加氯处理间', src='位置：图纸编号129标注点；' + EST)
add(id='ST-128', code='128', name='循环水管（压力钢管）', cat='cooling', shape='pipes', x=2901731.0, y=2549272.5,
    w=140, d=10, h=2, rot=0, area=5800, note='循环水进/回水压力钢管，布置于主厂房与冷却塔之间',
    src='位置：图纸编号128标注点（两处）；' + EST)

# ============ 输煤系统 ============
add(id='ST-130A', code='130', name='条形煤场（1#干煤棚）', cat='coal', shape='coalheap', x=2902270.4, y=2549107.6,
    w=45, d=132, h=14, rot=0, area=5940, note='条形贮煤场，挡煤墙围护，堆放高度约14m',
    src='平面轮廓：图纸实测矩形 (2902247.9,2549041.6)-(2902292.9,2549173.6)；一览表煤场及干煤棚合计30000m²')
add(id='ST-130B', code='130', name='条形煤场（2#干煤棚）', cat='coal', shape='coalheap', x=2902315.4, y=2549107.6,
    w=45, d=132, h=14, rot=0, area=5940, note='与1#并列',
    src='平面轮廓：图纸实测矩形 (2902292.9,2549041.6)-(2902337.9,2549173.6)')
add(id='ST-130C', code='130', name='挡煤墙', cat='coal', shape='retaining', x=2902348.5, y=2549120.0,
    w=1, d=130, h=3, rot=0, area=130, note='煤场东侧挡煤墙，钢筋混凝土',
    src='位置：图纸“挡煤墙”标注点(2902359,2549140)；墙线沿煤场东缘南北向布置')
add(id='ST-130D', code='130', name='圆形封闭煤仓（1#）', cat='coal', shape='dome', x=2902045.9, y=2549429.3,
    d=72, h=55, rot=0, area=4071,
    note='圆形封闭贮煤仓，穹顶钢结构；仓外设环形道路（图纸R40环形道）',
    src='平面轮廓：图纸R36圆弧实测，直径72m；功能定位为煤仓系按相邻输煤设施推判，' + EST)
add(id='ST-130E', code='130', name='圆形封闭煤仓（2#）', cat='coal', shape='dome', x=2902147.4, y=2549519.3,
    d=72, h=55, rot=0, area=4071, note='与1#同型，中心距100m',
    src='平面轮廓：图纸R36圆弧实测，直径72m；' + EST)
add(id='ST-131', code='131', name='干灰库', cat='aux', shape='tank', x=2901964.5, y=2548930.3,
    d=17, h=30, rot=0, area=225, note='钢筋混凝土灰库（Ф15m，有效容积约3000m³），下设散装机',
    src='位置：图纸编号131标注点；' + EST)
add(id='ST-132', code='132', name='气化风机房', cat='aux', shape='box', x=2902035.8, y=2548922.7,
    w=15, d=10, h=8, rot=0, area=150, note='气力除灰气化风机及灰库配电', src='位置：图纸编号132标注点；' + EST)

# ============ 水处理及辅助 ============
add(id='ST-133', code='133', name='制氢站', cat='aux', shape='box', x=2902067.2, y=2549292.7,
    w=31.5, d=31.5, h=9, rot=0, area=992,
    note='包含制氢间、储氢罐及配电间，防爆围栅围护',
    src='平面轮廓：图纸实测矩形 (2902051.5,2549277.0)-(2902083.0,2549308.5)，31.5×31.5m，与一览表1000m²吻合')
add(id='ST-134', code='134', name='化水除盐间及屋外设备', cat='aux', shape='box', x=2902040.4, y=2549247.8,
    w=24.4, d=25.5, h=12, rot=0, area=622,
    note='化学水处理除盐间，屋外布置除盐水箱与混床',
    src='平面轮廓：图纸实测矩形 (2902028.2,2549235.0)-(2902052.6,2549260.5)')
add(id='ST-135', code='135', name='净水站', cat='aux', shape='box', x=2902119.6, y=2549404.5,
    w=50, d=44, h=12, rot=0, area=2180, note='原水预处理（混凝沉淀+过滤），含加药间与泵房',
    src='位置：图纸编号135标注点；2180m²取一览表，按50×44m布置' + EST)
add(id='ST-136', code='136', name='卸煤槽（火车卸煤）', cat='coal', shape='pit', x=2901250.0, y=2548950.0,
    w=90, d=12, h=6, rot=0, area=1080,
    note='铁路专用线进入厂区的翻车机/螺旋卸煤槽，西侧接铁路线；图中仅见铁路线未标注卸煤槽编号',
    src='图中未见139/136明确标注点，位置按图纸铁路线及输煤系统走向推定，' + EST)

# ============ 一期生活及既有设施 ============
add(id='ST-C01', code='一期', name='食堂', cat='living', shape='box', x=2901345.9, y=2548995.6,
    w=30, d=15, h=9, rot=0, area=450, note='职工食堂（既有）', src='位置：图纸“食堂”标注点；' + EST)
add(id='ST-C02', code='一期', name='宿舍楼', cat='living', shape='box', x=2901263.2, y=2548990.6,
    w=60, d=15, h=18, rot=0, area=900, note='单身宿舍楼（既有）', src='位置：图纸“宿舍”标注点；' + EST)
add(id='ST-C03', code='一期', name='停车场', cat='living', shape='pad', x=2901247.9, y=2548948.7,
    w=90, d=16, h=0.2, rot=0, area=1100, note='职工停车场', src='位置：图纸“停车场”标注点')
add(id='ST-C04', code='一期', name='水池', cat='aux', shape='pit', x=2901378.2, y=2549149.4,
    w=60, d=20, h=3, rot=0, area=1200, note='施工/消防水池', src='位置：图纸“水池”标注点')

# ============ 施工临建区 (图纸“施工临建布置”图层, 位置为标注点) ============
CONS = [
 ('S-01', '设备堆放场四', 2901505.1, 2549542.1, 14000, 90, 155, 'pad', '临时设备堆场，场地平整+硬化'),
 ('S-02', '构件预制场', 2901497.0, 2549481.5, 5200, 60, 87, 'pad', '预制构件生产场地'),
 ('S-03', '阀门库', 2901444.6, 2549470.6, 400, 16.9, 25.2, 'box', '单层库房'),
 ('S-04', '机工具、劳保及耗材库', 2901463.5, 2549469.7, 380, 16.9, 25.2, 'box', '单层库房'),
 ('S-05', '五金水暖器材库/暖库/电控设备库', 2901422.5, 2549468.5, 1000, 30, 34, 'box', '单层库房'),
 ('S-06', '热机设备库', 2901384.1, 2549425.2, 2100, 40, 52, 'box', '单层库房'),
 ('S-07', '仓库区及机械动力站', 2901404.4, 2549407.2, 12000, 80, 150, 'pad', '仓库及机械动力站场地'),
 ('S-08', '维修间', 2901365.0, 2549383.6, 300, 24, 12, 'box', '单层维修间'),
 ('S-09', '钢筋木工场', 2901602.6, 2549200.5, 4400, 55, 80, 'pad', '钢筋加工及木工场地'),
 ('S-10', '模板制作维修间', 2901599.6, 2549223.3, 300, 30, 10, 'box', '临时棚架'),
 ('S-11', '钢筋加工间', 2901582.2, 2549220.9, 300, 30, 10, 'box', '临时棚架'),
 ('S-12', '锅炉组合场', 2901525.6, 2549131.8, 8600, 80, 108, 'pad', '锅炉受热面组合场地'),
 ('S-13', '汽管及六道组合场', 2901513.4, 2549082.9, 8600, 80, 108, 'pad', '汽水管道及烟风道组合场'),
 ('S-14', '施工办公室', 2901440.5, 2549079.9, 600, 62, 13, 'box', '两层活动板房'),
 ('S-15', '施工办公区', 2901391.2, 2549067.5, 6700, 80, 84, 'pad', '施工管理办公区'),
 ('S-16', '施工班房区', 2901540.8, 2549041.7, 4100, 60, 68, 'pad', '施工班组生活区'),
 ('S-17', '车辆停放场', 2901379.8, 2549079.6, 1500, 40, 38, 'pad', '施工车辆停放'),
 ('S-18', '重大件堆场', 2901631.8, 2548996.7, 1000, 30, 34, 'pad', '发电机定子等重大件堆场'),
 ('S-19', '预埋件预制场', 2901631.5, 2548933.1, 3000, 50, 60, 'pad', '预埋件制作场'),
 ('S-20', '花木公司', 2901481.8, 2548940.6, 800, 30, 27, 'pad', '绿化苗圃'),
 ('S-21', '一期施工办公室（留用）', 2901728.5, 2548938.5, 3000, 60, 50, 'pad', '既有临时办公区'),
 ('S-22', '施工生活区', 2902162.6, 2548939.4, 22000, 130, 170, 'pad', '施工人员生活区'),
 ('S-23', '设备堆放场二', 2901581.2, 2548783.8, 14000, 100, 140, 'pad', '设备堆场'),
 ('S-24', '设备堆放场一', 2902082.3, 2548775.9, 14000, 100, 140, 'pad', '设备堆场'),
 ('S-25', '设备堆放场三', 2901962.0, 2548878.8, 52500, 200, 262, 'pad', '大型设备堆场（图纸带剖面线区域）'),
 ('S-26', '业主商品砼站', 2901491.0, 2548688.3, 2000, 45, 44, 'pad', '商品混凝土搅拌站'),
]
for code, name, x, y, area, w, d, sh, note in CONS:
    add(id='ST-' + code, code=code, name=name, cat='construction', shape=sh, x=x, y=y,
        w=w, d=d, h=(6 if sh == 'box' else 0.4), rot=0, area=area,
        note=note, src='位置：图纸“施工临建布置”图层标注点；平面尺寸按标注面积换算' + EST)

# ============ 第二轮核查补录（图面实测但首版遗漏的建构筑物） ============
EXTRA = json.load(open(r'D:\test\.dwgconv\extra.json', encoding='utf-8'))
for x in EXTRA:
    add(**x)
print('extra structures', len(EXTRA))

# ---- 道路 (图纸 道路/NEW道路 图层双线配对抽取) ----
road_polys = [[[p[0], p[1]] for p in q[:4]] for q in ROADS]

# ---- 厂区围墙/边界 (按图纸用地范围简化) ----
boundary = [
 [2901130, 2549560], [2901830, 2549560], [2901840, 2549520], [2901960, 2549520],
 [2902050, 2549565], [2902130, 2549565], [2902170, 2549520], [2902300, 2549510],
 [2902420, 2549480], [2902420, 2548900], [2902200, 2548900], [2902140, 2548620],
 [2901900, 2548500], [2901600, 2548600], [2901500, 2548800], [2901200, 2548880],
 [2901130, 2549000], [2901130, 2549560]]

meta = dict(
    title='某电厂2×600MW扩建工程（二期）三维总平面',
    source='某电厂总平面规划图CAD图.dwg (AutoCAD 2007, AC1021)',
    unit='米（1图纸单位=1m，经冷却塔面积标定验证）',
    origin={'e': 2900800, 'n': 2548300},
    note='平面坐标采用图纸测量坐标（东E/北N）。冷却塔半径51m由图纸bulge=1半圆多段线反算，'
         '与一览表“循环水冷却塔16400m²”吻合，据此确定全图比例为1:1（米）。')

js = ['// plant-data.js —— 电厂总平面数据（由图纸 DWG 解析 + 人工校核生成，请勿手工改动坐标）',
      '// 坐标系：x/y 为图纸测量坐标（东E/北N，单位 m），由 main.js 减去 meta.origin 得到世界坐标；z 为高度。',
      '// 数据来源：某电厂总平面规划图CAD图.dwg 实体解析（entities.json, 11822 个实体）。',
      '(function (global) {',
      "  'use strict';",
      '  var PLANT_DATA = {',
      '    meta: ' + json.dumps(meta, ensure_ascii=False) + ',',
      '    structures: [']
for s in S:
    js.append('      ' + json.dumps(s, ensure_ascii=False) + ',')
js.append('    ],')
js.append('    roads: ' + json.dumps(road_polys, ensure_ascii=False) + ',')
js.append('    boundary: ' + json.dumps(boundary, ensure_ascii=False) + ',')
js.append('    trees: ' + json.dumps(trees, ensure_ascii=False) + ',')
js.append('  };')
js.append('  global.PLANT_DATA = PLANT_DATA;')
js.append('})(typeof window !== "undefined" ? window : this);')
open(OUT, 'w', encoding='utf-8').write('\n'.join(js) + '\n')
print('structures', len(S), 'roads', len(road_polys), 'trees', len(trees))
print('written', OUT, os.path.getsize(OUT), 'bytes')
