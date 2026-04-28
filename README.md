#gradlekts
plugins {
    application
}

repositories {
    mavenCentral()
}

dependencies {
    testImplementation(libs.junit)
    implementation(libs.guava)
}

java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(21)
    }
}

application {
    mainClass = "org.example.App"
}


tasks.named<JavaExec>("run") {
    standardInput = System.`in`
}

#java
package org.example;

import java.util.Scanner;

public class App {

    public static void main(String[] args) {

        Scanner sc = new Scanner(System.in);

        System.out.println("Enter Team 1:");
        String team1 = sc.nextLine();

        System.out.println("Runs:");
        int r1 = sc.nextInt();

        sc.nextLine(); // fix input issue

        System.out.println("Enter Team 2:");
        String team2 = sc.nextLine();

        System.out.println("Runs:");
        int r2 = sc.nextInt();

        if (r1 > r2)
            System.out.println(team1 + " wins");
        else if (r2 > r1)
            System.out.println(team2 + " wins");
        else
            System.out.println("Draw");

        sc.close();
    }
}
