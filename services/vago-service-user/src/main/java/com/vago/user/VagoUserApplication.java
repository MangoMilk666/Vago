package com.vago.user;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
@MapperScan("com.vago.user.mapper")
public class VagoUserApplication {
    public static void main(String[] args) {
        SpringApplication.run(VagoUserApplication.class, args);
    }
}
