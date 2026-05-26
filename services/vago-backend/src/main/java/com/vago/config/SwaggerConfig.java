package com.vago.config;

import io.swagger.v3.oas.models.Components;
import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.security.SecurityRequirement;
import io.swagger.v3.oas.models.security.SecurityScheme;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * SpringDoc OpenAPI 文档配置
 */
@Configuration
public class SwaggerConfig {

    private static final String SECURITY_SCHEME_NAME = "Bearer Token";

    @Bean
    public OpenAPI vagoOpenAPI() {
        return new OpenAPI()
                .info(new Info()
                        .title("Vago 后端 API")
                        .description("叠迹平台 REST API —— 用户、行程、足迹、设置等 CRUD 接口")
                        .version("v0.1"))
                .addSecurityItem(new SecurityRequirement().addList(SECURITY_SCHEME_NAME))
                .components(new Components()
                        .addSecuritySchemes(SECURITY_SCHEME_NAME, new SecurityScheme()
                                .name(SECURITY_SCHEME_NAME)
                                .type(SecurityScheme.Type.HTTP)
                                .scheme("bearer")
                                .bearerFormat("JWT")));
    }
}
