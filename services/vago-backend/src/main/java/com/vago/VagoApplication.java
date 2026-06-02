package com.vago;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * Vago 单体后端启动入口
 * 扫描 com.vago 下所有域的 Mapper（user、travel、geo……）
 */
@SpringBootApplication
@EnableScheduling
@MapperScan("com.vago.**.mapper")
public class VagoApplication {

    public static void main(String[] args) {
        SpringApplication.run(VagoApplication.class, args);
    }
}
