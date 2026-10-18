SweepPluck v3.1 — 可翻面的正交分体键盘
======================================

电池与电源开关焊接图
  见 power-guide/README.md，含左手 F 面、右手 B 面焊盘图及焊接检查步骤。
  电池正极接 BATP1/BAT，负极接 BATG1/GND；开关 2–3 脚控制 BAT 到 RAW。

旅行便携盒
  travel-case/ 为裸 PCB + 3 mm 防滑垫配置的便携盒模型与 EVA 内托裁切图。
  轴体按 Choc V2，键帽高度按 K3 兼容矮键帽 4.4 mm 估算，主控为插座安装的 nice!nano。
  合拢外形约 108.05×92.80×44.80 mm；使用外部魔术贴绑带闭合。
  具体尺寸预算、安装限制和打印说明见 travel-case/使用说明.txt。
  tools/travel_case.py 可调整高度与主控安装间距预算；尚未实物试印。
  case/ 是之前的可选键盘底壳方案，使用上述旅行盒不需要制作该底壳。
  下方原有 ZIP 为此前生成的归档，不包含本次新增旅行盒，以目录中当前文件为准。

打开 SweepPluck.kicad_pro。
嘉立创 PCB 下单上传 SweepPluck-JLCPCB.zip。
它只包含 9 个生产层/钻孔文件，均位于 ZIP 根目录。
现在是一款 17 键单侧 PCB，同一份 Gerber 制作两片：
一片在 F 面安装键轴作为左手，另一片在 B 面安装键轴作为右手。
每片板都包含两种装配方式所需的孔和焊盘，不需要左右专用板。
原 v2 双侧拼板完整保存在 archive/SweepPluck-v2-panel.zip。

尺寸与布局
  整套 34 键，每侧 3×5 主键，加内侧第四排 2 个水平拇指键。
  键位与 v2 相同，全部为 0°，横纵键距均为 19.05 mm。
  单片 PCB 板框中心线尺寸：95.25×80.0 mm。
  板高由 77 mm 增至 80 mm，用于容纳主控的两组选装孔排。
  Gerber job 包围盒包含 0.05 mm 板框线宽，显示 95.30×80.05 mm。
  PCB 为 2 层 FR-4、1.6 mm 厚；USB/TRRS 插座可向板边外伸出。
  每片板有两个 3.2 mm 安装孔，仍位于原主键网格交点。
  此版本交付单片板；整套使用两片相同 PCB，没有折断桥。

装配方法
  左手：将丝印 LEFT 的 F 面朝上，在此面装轴体、TRRS、电源及复位开关。
        主控装在 U1 的两排 L 孔中，USB 朝左侧外缘。
  右手：将丝印 RIGHT 的 B 面朝上，在此面装上述器件。
        主控装在同一 U1 封装的两排 R 孔中，USB 朝右侧外缘。

  主控区域共有四条横向孔排，按布局图方向从上到下依次为 L、R、L、R。
  左手选第 1 和第 3 排，右手选第 2 和第 4 排。
  两组选装孔排整体错开 2.54 mm，孔径为 1.0 mm。
  每组都是完整的 2×12 针 Pro Micro 接口，每块 PCB 只装一个主控。
  不需要 MCU 焊锡跳线，也不要短接另一组选装孔排。

  主控沿用 Sweep High M 的 FACE DOWN 安装方向：
  元件面、USB 插座所在面朝向键盘 PCB，而不是朝向键帽上方。
  用排针或插座留出元件和 USB 外壳的高度，不要将主控模块贴板焊接。
  两面均标有 FACE DOWN、L/R、TX 和 RAW，可用模块引脚标记核对方向。
  左手 L 组 USB 端的上排是 TX、下排是 RAW；
  右手 R 组从 B 面看 USB 端的上排是 RAW、下排是 TX。
  电源和复位开关均提供 F/B 两面焊盘，每个位置只在键轴所在面安装一个。
  轴体焊孔、TRRS 成对焊盘和电池通孔支持正反面装配。

轴体与电路
  保留原 Choc V1 / Choc V2 / MX / Alps 通用焊接兼容性，无热插拔。
  新轴体封装保留原钻孔中心并增加镜像孔位。
  MX/Alps 的两个无极性触点翻面后交换 GPIO/GND 接法；
  Choc 的中心触点仍接 GND，左右对称的另一触点接同一 GPIO。
  重叠的轴体圆孔/长孔已合并为连续镀铜长孔。
  中心定位孔为 4.9 mm，两侧定位孔仍为 2.17×1.8 mm NPTH 长孔。
  每侧 17 键直连，无矩阵二极管。
  两组选装孔的 24 针 GPIO、电源和复位映射均与 v2 左侧一致。
  每侧 68 个有效器件引脚连接与原设计核对一致。
  TRRS：R1=SERIAL（Pro Micro RX），R2=VCC，T/S=GND。
  电池正极 BAT 经电源开关接 RAW，负极接 GND，沿用原供电接法。
  引脚 CSV 包含网络、坐标、钻孔和 LEFT/RIGHT/BOTH 装配标记。
  预览数字 1–17 是 Switch1–Switch17 网络编号，不是实际键码。
  本次没有新增或烧录固件；左右手选择由对应 QMK/ZMK 固件配置。

定位板
  SweepPluck-plate.kicad_pcb / .dxf 是可翻面的单侧定位板，DXF 单位为毫米。
  两侧各用一片相同定位板，右手翻面使用。
  下方外侧开口避让两组选装主控及其他器件。
  默认 14×14 mm 轴孔供适配该尺寸的 MX/Choc 使用。
  Alps 定位板开口不同，使用 Alps 时需按实际轴体另改定位板。
  网格交点上的固定件需低于键帽活动空间，可使用平头/沉头方案。

交付文件
  SweepPluck-v3-reversible.zip：完整 v3 工程包，包含本地库、脚本、检查报告和来源归档。
  SweepPluck.kicad_pro / .kicad_pcb / .kicad_sch：v3 主工程。
  SweepPluck.kicad_sym、SweepPluck.pretty、库表：本地符号与可翻面封装。
  SweepPluck-preview.png / SweepPluck-layout.svg：左右手装配示意。
  SweepPluck-preview.svg / SweepPluck-preview-pcb.png：实际 F 面 PCB。
  SweepPluck-back.svg / SweepPluck-back-pcb.png：镜像显示的实际 B 面 PCB。
  SweepPluck-plate.kicad_pcb / .dxf / .svg：单侧定位板。
  SweepPluck-pins.csv：引脚、网络和孔排核对表。
  SweepPluck-JLCPCB.zip / SweepPluck-gerbers.zip：相同的专用下单包，共 9 文件。
    包含两面铜层、阻焊、丝印、GKO 板框和独立 PTH/NPTH 钻孔。
    使用标准 RS-274X、Protel 扩展名、毫米十进制 Excellon，绘图坐标为非负值。
    不含工程、嵌套压缩包、Gerber job 或 X2/网络扩展属性。
  gerbers/：KiCad 原始导出文件，另外保留一个 Gerber job，目录共 10 文件。
  verification/summary.json：最终检查结果与板文件、生产文件 SHA-256。
  verification/fabrication-check.json：对实际下单 ZIP 的独立 Gerbv 解析及开窗/钻孔核对报告。
  archive/SweepPluck-v2-panel.zip：改动前双侧拼板及全部配套文件。
  archive/SweepPluck-v1-split.zip：更早的左右独立工程。

验证与限制
  KiCad 10.0.7：PCB DRC 0 违规、0 未连接、0 原理图一致性问题。
  原理图 ERC 0 违规，定位板 DRC 0 违规。
  102 项触点检查覆盖每个键的 MX、Alps、Choc 两面安装接法。
  原 153 个轴体钻孔中心全部保留，原键位与 GPIO 映射核对通过。
  主控外形与键帽、定位板避让区核对通过。
  v3.1 修复了布线导入后通孔焊盘阻焊开窗丢失的问题。
  211 个通孔焊盘均有双面开窗；每面导出的 277 个开窗逐项核对通过。
  专用包 9 文件经 Gerbv 2.10.0 独立解析：0 错误、0 警告。
  镀铜钻孔/槽 222 个（包含过孔），非镀铜孔/槽 57 个，与 PCB 数量一致。
  尚未在嘉立创账户中完成在线上传实测。
  线宽 >=0.20 mm、电气间距 >=0.20 mm、铜到板边/钻孔 >=0.25 mm。
  走线为 0.25 mm，过孔为 0.60/0.30 mm。
  原理图为被动引脚连接图，ERC 不检查 MCU 引脚方向或模块供电/充电能力。
  尚未实物打样；插座高度、实际模块外形及轴体/定位板装配仍需打样确认。

重新生成（当前文件已生成，无需运行）
  使用能 import pcbnew 的 KiCad Python，并确保 kicad-cli 位于 PATH。
  cairosvg 用于 PNG 预览，布线需 Java 21 和 Freerouting 2.1.0。
  从仓库根目录运行：
    python SweepPluck/tools/reversible.py build
    python SweepPluck/tools/reversible.py route --jar /path/to/freerouting-2.1.0.jar
    python SweepPluck/tools/reversible.py import
    python SweepPluck/tools/reversible.py checks
  build 从 v2 归档重建 v3，会覆盖 PCB 为未布线版。
  若 checks 仅有 track_dangling 警告且无未连接项，运行：
    python SweepPluck/tools/reversible.py clean
  clean 只移除 DRC 明确报告的冗余支线，不忽略检查项。
  完成后：
    python SweepPluck/tools/reversible.py placement
    python SweepPluck/tools/reversible.py export
    python SweepPluck/tools/check_fabrication.py
  export 会先核对检查报告与当前 PCB、原理图、定位板及规则，再导出生产文件。
  check_fabrication 需安装 gerbv，检查专用下单包的实际文件与 PCB 数据。
  手动编辑 PCB 后可用 refresh 更新辅助文件，再执行 checks 和 export。
  compact.py 转发到同一 v3 生成器；preview.py 生成 v3 装配图。
  如需重新打包完整工程，运行 python SweepPluck/tools/package.py。

参考与授权
  原接口/键位来源为本仓库 Sweep High；可翻面结构参考 Sweep High M / Sweep Half Swept。
  主控安装方向参考 gallery/sweep-high-m/front.png 的 Face down 标记。
  nice!nano 引脚图：https://nicekeyboards.com/docs/nice-nano/pinout-schematic/
  Freerouting：https://github.com/freerouting/freerouting/releases/tag/v2.1.0
  授权沿用本仓库 LICENSE。

