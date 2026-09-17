# iOS Footprint Module

本目录汇总 iOS Travel Map / Travel Tracking 的模块文档。

- [设计说明](design.md)：地图、定位、轨迹、打卡和 World Fog 的产品与技术边界。
- [实施计划](implementation-plan.md)：基于当前工程的分阶段实现、风险和真机验收方式。

该模块收集 GPS、轨迹和手动打卡等真实旅行观察数据。它们是 Personal Travel Context 的事实来源；iOS 不承载 Agent Runtime，也不负责推断或改写旅行事实。
