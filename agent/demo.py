from datetime import datetime, timezone

def demo_report():
    rows=[
      ('多家媒体关注中国新能源产业与全球供应链','Reuters · 示例','科技与贸易','中性',92,'报道讨论新能源供应链及贸易政策。待核查：出口数据的统计口径和政策生效时间。','出口增长数据是否采用同一统计期间？'),
      ('社媒流传中国城市现场视频，拍摄时间尚待确认','X · 示例','社会与文化','待研判',88,'视频被用于解释近期事件，尚未获得原始文件。核查重点：最早发布记录、地标、拍摄时间及剪辑情况。','视频是否拍摄于所声称的日期及地点？'),
      ('涉华贸易政策讨论升温，数字与表述需要交叉比对','BBC · 示例','科技与贸易','负面',83,'评论涉及关税及产业补贴。负面立场不等于事实错误；需把评论观点与可验证的数据主张分开。','关税比例是否覆盖所有商品？'),
      ('国际机构发布亚洲经济展望，中国增长预期受关注','Bloomberg · 示例','经济与市场','中性',79,'关注增长预期与经济指标。需要对照原始报告，区分预测与实际值，核实发布日期和修订版本。','被引用的数据是预测值还是已公布实际值？'),
      ('中国入境旅游话题在海外平台获得更多讨论','SCMP · 示例','社会与文化','正面',71,'讨论签证便利和旅行体验。个人体验具有样本限制，相关政策须对照正式公告及适用范围。','政策是否适用于帖子中提到的全部国籍？'),
      ('涉华安全议题报道出现匿名信源与未公开材料','The Guardian · 示例','地缘政治','负面',68,'报道包含匿名信源的指控。当前无可独立验证材料，结论为证据不足，需寻找公开原始记录与独立证据。','匿名信源所述事件是否有公开记录佐证？'),
    ]
    items=[]
    for i,(title,source,topic,sentiment,score,summary,claim) in enumerate(rows):
        items.append({'id':f'demo-{i}','title':title,'source':source,'topic':topic,'sentiment':sentiment,'score':score,'summary':summary,'claims':[claim],'url':'','published':'演示数据 · 非真实报道','risk':'待核查','risk_score':0,'risk_hint':'演示核查任务，未作事实判断','verdict':'证据不足','analysis_method':'演示示例','evidence':[],'description':''})
    return {'id':'demo','date':datetime.now(timezone.utc).strftime('%Y-%m-%d'),'created_at':datetime.now(timezone.utc).isoformat(),'demo':True,'items':items,'errors':[],'stages':[]}
