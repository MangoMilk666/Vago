# iOS Footprint Module

本目录汇总 iOS Travel Map / Travel Tracking 的模块文档。

- [设计说明](design.md)：当前地图、定位、轨迹与打卡的稳定语义；World Fog 仍是未来实验。
- [后续验收与实施计划](implementation-plan.md)：待做的真机、浏览器与性能验证，以及按证据触发的后续工作。
- [历史快照](../../../archive/README.md)：旧 Phase 1–6 的完整过程和清理前的详细设计。

该模块收集 GPS、轨迹和手动打卡等真实旅行足迹数据。它们是 Personal Travel Context 的事实来源；iOS 不承载 Agent Runtime，也不负责推断或改写旅行事实。
